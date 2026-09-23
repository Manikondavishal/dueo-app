# Dueo — PRD & Build Log

## Original problem statement
Invite-only SaaS that helps Indian service businesses get paid by automatically
following up on overdue invoices (email first). Pilot: India/INR only, times in
Asia/Kolkata (store UTC), money as integer paise. One login per business
(MAX_MEMBERS_PER_ORG=1). Email is the main channel; WhatsApp/Razorpay/Shield are OFF.
Build Phase 0 (infra proof) then Phase 1 (invite→login→setup→Today shell), then stop.

## Stack & architecture
- React (CRA) + React Router + Tailwind + custom Dueo design system (`dueo.css`).
- FastAPI (Python 3.11, Pydantic v2) packaged under `backend/app/{config,util,models,security,deps,main}` +
  `{routers,services,repositories,providers,jobs,migrations}`. Entry: `server.py` → `app.main:app`.
- MongoDB via Motor. **Only `app/repositories/` touches the DB** (enforced by `tests/test_repo_boundary.py`).
- Auth: passwordless email-OTP + httpOnly `dueo_session` cookie (30d). No passwords.
- Audit: append-only hash-linked chain with `verify_audit_chain()` + daily anchor.
- Scheduler: in-app APScheduler (every-minute tick with atomic job claim; daily 00:10 IST anchor) +
  platform crons in `.emergent/crons.yml` (day-5 reminders, audit anchor).
- Integrations: Emergent-managed Resend (email), Gemini 3 Flash via `LLMProvider` (image→JSON),
  Emergent object storage (uploads).

## Personas
- **Business owner** (Indian service business): requests invite, signs in, sets up, sees Today.
- **Platform admin** (ADMIN_EMAILS): reviews leads (approve/hold/reject/resend), manages users, reads outbox.

## Ops notes
- **Section 2 (Choose-how-to-proceed) shipped 2026-09-23**: new
  `POST /api/hubs/{id}/handling` with body `{mode: "share_myself"|"dueo_handles"}`,
  writes `handling_mode` on the draft hub. `400 invalid_mode` on anything else,
  `409 hub_not_draft` once status leaves draft, `401` unauth, `404` cross-org.
  Frontend `/hub/:id/proceed` shows two big option cards (butter/mint tones,
  Dueo characters); on "share_myself" a copyable link panel appears with
  `{REACT_APP_BACKEND_URL}/hub/{public_token}` + Copy button + "Actually let
  Dueo handle it" switch; on "dueo_handles" routes to `/hub/:id/contacts`
  (Section 3 target). **Evidence**: authenticated POST returned the updated hub
  with `handling_mode=share_myself`, invalid mode → 400, unauth → 401, non-draft
  → 409. UI screenshot verified all `data-testid` hooks + copyable public URL.
- **P3 (Preview screen) shipped 2026-09-23**: `/hub/:id/preview` renders a
  read-only case card (status pill computed from `due_date` — `N days overdue` /
  `Due today` / `Due in N days`), giant amount, client name, INV # / Due /
  Currency / LLM grid, payment details block, plus a lilac "What {client} will
  see" mini-preview card. **Continue** button disabled until every required
  field is present; **Edit details** returns to Review. No new backend — pure
  read of `GET /api/hubs/{id}`. Screenshot verified all 10 `data-testid` hooks
  present with a real overdue Kestrel Logistics case (₹85,000 · 16 days overdue).
- **P2 (Review screen) shipped 2026-09-23**: `PATCH /api/hubs/{hub_id}` (auth,
  tenant-scoped, `409 hub_not_draft` once status leaves draft). Accepts
  `amount_rupees` (float ≥ 0) and stores integer paise. Frontend `/hub/:id/review`
  page has a two-column form for invoice number / client / amount / currency /
  due date + a full-width "How you get paid" textarea. Client-side validation
  blocks empty fields and bad date format; on success routes to `/hub/:id/preview`
  (P3 stub). **Evidence**: authenticated PATCH round-trip changed all fields, GET
  returned the new values, unauth PATCH returned 401, PATCH on a non-draft hub
  returned 409. Screenshot shows the page pre-filled from the LLM-extracted hub
  (`INV-0417 / Kestrel Logistics / 85000 / 2026-09-07`).
- **P1 (invoice upload UI) shipped 2026-09-23**: `POST /api/hubs/from-upload`
  ties together the existing Phase-0 object-storage upload + Gemini LLM extract,
  creates a draft `payment_hub` with extracted fields (invoice_number, client_name,
  amount_paise, currency, due_date). Frontend `/upload` page (auth-required) has
  drag-drop + progress + extracted-field preview + "Review the details" CTA.
  Also wired `Today.jsx`'s "Add invoice" button to `/upload`. PDF uploads persist
  but skip LLM extract (llm_status=skipped); user fills fields manually in Review.
  **Evidence**: E2E script uploaded a synthetic invoice PNG as
  `phase0_upload@example.com`, Gemini returned exactly the fields painted on the
  image (INV-0417 / Kestrel Logistics / ₹85,000 / INR / 2026-09-07),
  amount coerced to 8500000 paise, hub row persisted with status=draft.
- **Twilio WhatsApp pipe (P0 + P4) shipped 2026-09-23**: `WhatsAppProvider` interface,
  `TwilioWhatsAppProvider` (real, async) + `LogOnlyWhatsAppProvider` (fallback when
  Twilio creds are missing), inbound webhook at `/api/webhooks/twilio-whatsapp/inbound`
  and delivery-status webhook at `/api/webhooks/twilio-whatsapp/status`. Signature
  verification uses `X-Forwarded-Host` (trusted-suffix guarded) + forced `https` +
  request path — required because the preview ingress presents an internal cluster
  host to the app. Rows are upserted by `provider_sid` so Twilio retries do not
  duplicate. Sandbox creds active (`ORG_WHATSAPP_FROM=whatsapp:+14155238886`).
- **Section 1 collections shipped 2026-09-23**: `whatsapp_messages`, `payment_hubs`,
  `payment_hub_contacts`, `follow_up_plans`, `follow_up_messages` with indexes.
  `whatsapp_messages.payment_hub_id` is nullable so inbound test rows fit.
- **Emergent-managed email key is currently invalid** (`EMERGENT_EMAIL_KEY` returns
  `401 invalid X-Email-Key` from `integrations.emergentagent.com`). Real OTP emails
  do NOT deliver until the user rotates the key. The outbox still records every send.
- **Admin sign-in bootstrap**: `GET /api/admin/bootstrap-code?email=<admin>&token=<CRON_SECRET>`
  returns the last OTP for an admin email — works even when the mailer is down.
- Landing page: hero "Dueo noticed" card lifts on hover (no longer covers the
  chat bubble text); replaced the old Control section with **Peek inside** —
  a 3-tile showcase of Today view, Invoices, and Proof of promise (uses the
  attached PNG artifacts from customer-assets).

## What is implemented (2026-09-20)
- Phase 0 (all PASS, see `docs/PHASE0_REPORT.md`): webhook HMAC+store-first, atomic single-winner job race,
  unique-index dedupe, auth-gated upload/download, LLM image→structured JSON.
- Phase 1: invite waitlist (honeypot, 5/hr IP limit, email-format, idempotent, manual_review routing,
  confirmation email); admin `/admin/leads` + `/admin/users` (suspend/restore, session revocation) + `/admin/outbox`;
  approve issues single-use 7-day invite link (hashed) + day-5 reminder cron; OTP login (neutral response,
  hashed codes, 10-min expiry, 5 attempts→15-min lock, per-email/IP limits, new code cancels old);
  invite-consume creates user+org+member and opens setup; Setup step 1 (name/mobile/Udyam optional/consent),
  steps 2–3 "Coming next"; Today shell (left rail, Channels "Not connected", empty state).
- Design: cream/ink palette, Bricolage/Instrument Serif/Geist/Geist Mono, pill buttons, `DueoCharacter`
  (5 bodies × 6 faces) + `ShieldCharacter`, gentle motion (reduced-motion aware). Full landing per PDF,
  responsive 390/768/1440, meta + Open Graph tags.
- Security: pydantic-settings fail-fast, CORS to app origin + regex, origin check on writes, CSP/HSTS/
  X-Frame-Options DENY/Referrer-Policy/X-Content-Type-Options, `/api/health`, structured JSON logs (no emails/codes).
- Tests: 13 backend pytest (repo boundary, tenant isolation, audit chain + tamper, auth flows, invite lifecycle)
  + testing-agent Phase 1 suite — 100% backend & frontend.

## Real vs stubbed
- **Real**: all auth/invite/admin/setup APIs & DB, audit chain, scheduler, webhook, uploads (object storage),
  LLM image→JSON, email (Resend send + outbox record).
- **Honest placeholders (by pilot design)**: Today stat cards show ₹0/empty (no invoices yet); Channels all
  "Not connected"; Invoices/Clients/Shield nav = "Coming next"; Setup steps 2–3 = "Coming next".
- **NOT built (per instructions)**: invoice upload UX, eligibility, follow-up plan, sending, client payment page,
  WhatsApp, Razorpay, Proof of promise, Shield logic.

## Backlog (next, awaiting go-ahead)
- P1: **Section 3 (Contacts)** — Primary/Escalation-1/Escalation-2 form at
  `/hub/:id/contacts` writing to `payment_hub_contacts`; primary all-required,
  escalations optional.
- P1: **Section 2 (Choose-how-to-proceed)** — two-path picker (share-myself
  vs Let-Dueo-handle-it).
- P1: **Section 3 (Contacts)** — Primary/Escalation-1/Escalation-2 UI writing to
  `payment_hub_contacts`.
- P1: **Section 4 (Tone & Approve)** — first real WhatsApp send via the pipe.
- P1: **Sections 5–7** — public /hub/:token page, /dashboard + /hub/:id/detail,
  delete /dev/whatsapp-test.
- P1: **Prerequisite UI still owed** — invoice upload UI (P1), review (P2),
  preview (P3). The Twilio pipe (P4) is done, but no user flow yet creates a
  `payment_hub` via UI; the round-trip test exercises the collections via the
  store directly.
- P2: Phase 2 — LLM field extraction into `invoices`, setup steps 2–3, real
  follow-up plan engine + email sending via the scheduler tick.
- P2: Rotate `EMERGENT_EMAIL_KEY` so real OTP/invite emails deliver.

## Deployment
- Env vars in `backend/.env` (+ `.env.example` mirror). GitHub Save + Deploy are user-triggered via the UI.
