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
- **2026-09-24 quality pass**: (a) stripped the sole emoji from
  `services/templates.py` (`("warm","initial")` no longer contains `👋`);
  audit confirmed zero emoji across all 9 templates. (b) `approve_plan` now
  snapshots the recipient into `follow_up_messages` (`contact_name`,
  `contact_phone`, `contact_email`) AND into the `whatsapp_messages` mirror
  (`to_name`) so a later Contacts replace cannot rewrite an already-sent
  message's history. New test `test_approve_snapshots_contact_at_send_time`
  proves the snapshot survives a full contacts overwrite. (c) new
  `test_dashboard.py` covers counts bucketing, conversation ordering (Dueo →
  client), outbound-WA dedupe, self-share info row, cross-org 404, unknown-hub
  404, and empty-org isolation — 6 tests, all green. Full suite: **59 passed**
  (52 → 59) in serial mode (`pytest -n 0`). Live E2E curl proof: admin login
  via bootstrap → `/api/app/dashboard` returns `active=1` + Zephyr Retail row
  → `/api/app/hubs/{id}/conversation` returns a 2-turn Dueo/Zephyr thread
  sorted oldest→newest. (d) `EMERGENT_EMAIL_KEY` still returns 401 — playbook
  confirms the exact stale key is what the platform hands us; user must
  contact `support@emergent.sh` to get a rotated key written into
  `backend/.env` (self-service rotation is not available for this integration).
- **Section 6 (Dashboard + Invoice detail) shipped 2026-09-23**: new
  `backend/app/routers/dashboard.py` mounted at `/api/app`:
  `GET /dashboard` returns 4 counts (`active`, `promises_due`,
  `needs_attention`, `paid_this_month`) plus a trimmed hub table + user + org
  payload; `GET /hubs/{id}/conversation` merges `follow_up_messages` (as
  "Dueo" sender) with inbound-only `whatsapp_messages` (as client name),
  optionally appends a self-share info row when `handling_mode="share_myself"`,
  and sorts oldest→newest. Outbound WhatsApp rows are skipped in the merge
  so the sent follow-up doesn't appear twice.
  Frontend `/dashboard` shows greeting + 4 colour-tiered count cards +
  clickable hubs table. `/hub/:id/detail` has 3 tabs — **Conversation**
  (chat-style bubbles: white for Dueo, mint for client, butter for
  self-share), **Details** (all fields at a glance), **Activity**
  (timestamps). Section 7 is a no-op: `/dev/whatsapp-test` was never built
  here so there's nothing to delete.
  **Evidence**: live curl on preview returned `counts={active:1,
  promises_due:0, needs_attention:0, paid_this_month:0}` with the seeded
  hub row; unauth → 401; conversation merger showed the Dueo bubble;
  cross-org → 404. Screenshots verified dashboard + detail (all 3 tabs)
  render with every `data-testid` present. Tenant isolation is separately
  covered by `test_tenant_isolation.py` in the pre-existing suite.
- **Section 5 (Public payment hub) shipped 2026-09-23**: new
  `backend/app/routers/public_hub.py` prefixed `/api/public/hub`.
  `GET /{token}` returns a **redacted** hub payload (no `org_id`, `upload_id`,
  `llm_status`, timestamps of internals) + a chronological timeline assembled
  from `follow_up_messages`, `whatsapp_messages`, hub `viewed_at`, and
  `client_response`. First GET also stamps `viewed_at` so the "Client opened
  this page" event lands automatically. `POST /{token}/confirm` records
  `{kind:confirmed, payment_date, submitted_at}` (400 on bad date).
  `POST /{token}/issue` records the note AND flips the hub to
  `status=disputed` so any future scheduler tick can skip it. `404` on any
  unknown token. Frontend `PublicHub.jsx` at `/hub/:token` — no Shell,
  cream background, hero card with **Pay now** (opens business payment
  details panel — no gateway), **Confirm payment date** (date picker) and
  **There's an issue** (textarea). Below: vertical timeline with colored
  dots per event kind + India-locale timestamps. All state changes refresh
  the timeline in-place.
- **Section 4 (Tone & Approve) shipped 2026-09-23**: new
  `services/templates.py` holds all 9 static templates (3 tones × 3 categories:
  `initial`, `follow_up`, `escalation`); `render()` does plain `{var}`
  substitution with `_fmt_inr()` for Indian rupees. New routes
  `GET /api/hubs/{id}/preview-messages?tone=` (returns all 3 categories rendered)
  and `POST /api/hubs/{id}/approve` (body `{tone, consent}`; `400 consent_required`
  / `bad_tone` / `no_primary_contact`, `409 hub_not_draft`). On approve:
  creates `follow_up_plans` (status=approved), inserts first
  `follow_up_messages` (category=initial, status=scheduled), dispatches via
  `providers.whatsapp.provider.send_freeform` to primary phone, on success
  updates row → status=sent + provider_sid + mirrors an outbound row in
  `whatsapp_messages`; on failure updates → status=failed + error preserved.
  Hub always flips to `status=active` so retries can run later. Frontend
  `/hub/:id/tone` has 3 tone cards (sky/mint/coral), 3 category tabs, WhatsApp
  preview card, consent checkbox on butter background, and a "Twilio sandbox
  join phrase required" callout in lilac.
  **LIVE proof**: `POST /approve` against the real Twilio sandbox returned
  `plan_status=approved`, `msg_status=failed`, `send_error="HTTP 422 …No
  Twilio trial phone number is assigned for messaging to this destination
  number"` — the sandbox specifically rejects unverified recipients, which
  confirms the code hits Twilio's live API with valid credentials; once the
  primary joins by texting the sandbox code, sends will deliver.
- **Section 3 (Contacts) shipped 2026-09-23**: new
  `GET /api/hubs/{id}/contacts` (prefill) and `POST /api/hubs/{id}/contacts`
  with replace-semantics — wipes the hub's existing rows and inserts the new
  set atomically. Body: `{poc, escalation_1?, escalation_2?}`; primary requires
  `name+phone+email`, escalations optional but must be fully valid if any field
  is filled. Server-side regex validates phone (`^\+?\d[\d\s\-]{6,}$`) and
  email; failures return `400 {role}_bad_{field}` or `_missing_{field}`. `409`
  on non-draft, `401` unauth, `404` cross-org. Frontend `/hub/:id/contacts` has
  three colour-tiered contact blocks (mint primary, butter esc1, lilac esc2)
  with inline "all three fields" hint; **Continue to tone →** is disabled until
  the primary is valid AND any filled escalations are valid. On save routes to
  `/hub/:id/tone` (Section 4 target). Store helper: `replace_hub_contacts`.
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

## Backlog (next, user-driven)
- P2: **Scheduler tick for follow-ups** — the follow_up_plan currently only
  fires the initial message; add a cron worker that reads
  `next_scheduled_follow_ups` and dispatches via `wa_provider`, respecting
  hub `status != "disputed"` and the 5-in-30-days cadence.
- P2: **Mark-as-paid flow** so `paid_this_month` count moves off 0.
- P2: **Rotate `EMERGENT_EMAIL_KEY`** so real OTP/invite emails deliver.
- P2: **Twilio production sender + template approvals** so we exit sandbox
  and can send to any WhatsApp number without join phrases.
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
