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
- **2026-09-25 retest green (iteration_3)**: testing agent verified 0 critical /
  0 minor. Both real accounts sign in and reach the dashboard (200), admin
  pages 200, `fix_owner_and_cleanup.py` idempotent, `bootstrap-code`
  `usable` flag correct (true while the OTP is live, false once consumed),
  security guards intact, lead list shows only the one real lead. Full suite
  **84 passed** serial. Fixes made after iteration_2: (i) the repair script is
  now symmetric — it re-creates a missing `organizations` doc for BOTH real
  accounts whenever a live membership row points at one (this was the
  CRITICAL 404 `org_not_found` on vishalmanikonda@icloud.com); (ii)
  `bootstrap-code` now returns `usable`, computed by hashing the extracted
  code against the live active OTP, so a stale/consumed code is never handed
  over as if it would work.
- **2026-09-25 owner account + bootstrap + lead cleanup + test-wipe bug**:
  (a) `whymancreates.studio@gmail.com` is now a real working owner — user set
  active, added to `ADMIN_EMAILS` (so /admin/* works) and given its own org
  "Whyman Creates" (the primary org was full at MAX_MEMBERS_PER_ORG=1).
  Live proof: request-code → bootstrap → verify 200 → `/api/app/dashboard`
  200 with empty counts, `/api/admin/leads` 200.
  (b) `GET /api/admin/bootstrap-code` no longer requires the address to be in
  ADMIN_EMAILS — any address, still guarded ONLY by `CRON_SECRET`
  (401 on bad token, 404 when no code exists). This is the workaround while
  `onboarding@resend.dev` mail lands in Gmail spam. New
  `tests/test_bootstrap_code.py` (4 cases).
  (c) Lead cleanup: `backend/fix_owner_and_cleanup.py` (idempotent) removes
  only obvious test rows (@example.com/@x.com/test-prefixed) — 485 → 1 real
  lead (`vishal@oddenough.in`, status `new`, never approved). Re-run it after
  any pytest run, which re-seeds test leads.
  (d) **Real bug found + fixed**: `tests/test_email_fallback.py` was wiping the
  ENTIRE `organizations` collection, which silently destroyed real signed-up
  accounts in the shared preview DB and left them 404 `org_not_found` on
  every request (this is what broke the earlier admin session twice). The
  fixture now deletes only its own `org_email_fb`. Verified: after a full
  suite run the "Whyman Creates" org survives and the dashboard still
  returns 200.
  (e) **WhatsApp is NOT working end to end**: a real send to +91 7013248755
  from the new sandbox number returned Twilio `422 "No Twilio trial phone
  number is assigned for messaging to this destination number. Please add
  the 'to' number as a verified recipient."` The Twilio Messages list is
  EMPTY and `whatsapp_messages` has 0 rows, so no join message ever reached
  the sandbox. The phone must send the sandbox join phrase to
  +1 737 250 8034 before any send or inbound webhook can work.
  Full suite: **74 passed** serial.
- **2026-09-25 LIVE EMAIL PROOF — real delivery confirmed**: own Resend key
  written to `backend/.env` (`RESEND_API_KEY`, 36 chars, `re_` prefix),
  backend restarted. Ran `backend/live_email_proof.py`, which refuses to run
  on an empty/malformed key, seeds an active user for the Resend
  account-owner address and then executes the REAL
  `services.auth.request_code` path. Result:
  `to=whymancreates.studio@gmail.com`, `from=Dueo <onboarding@resend.dev>`,
  outbox row `status=sent`, `provider_id=01a0d7d2-fb27-770a-affe-c6e121057cc6`.
  Independently confirmed against Resend's own API:
  `GET https://api.resend.com/emails/{id}` → 200 with
  `last_event="delivered"`, subject "Your Dueo sign-in code". This is a
  genuine delivery, not fixture data.
  Also probed the documented `resend.dev` restriction with a real call to a
  non-owner recipient — see the recorded outbox error; this is why a verified
  domain is still required before client follow-ups can land.
  NOTE: the key was pasted in chat, so it lives in conversation history —
  rotate it in Resend once WhatsApp + email are both signed off.
  Skipped per user: Verify Domain, Retry, Delivery Badges (until email +
  WhatsApp are both confirmed end to end).
- **2026-09-24 Email moved to OUR OWN Resend key**: `providers/email.py` now
  POSTs directly to `https://api.resend.com/emails` with
  `Authorization: Bearer $RESEND_API_KEY`, `User-Agent: dueo-api/1.0` (Resend
  403s direct calls without one) and `from = "Dueo <$RESEND_FROM>"`
  (`RESEND_FROM=onboarding@resend.dev`). The Emergent-managed pipe
  (`X-Email-Key` → `integrations.emergentagent.com/api/v1/email/send`) is
  fully removed from code; `EMERGENT_EMAIL_KEY` remains in `.env` only as a
  dead legacy value. Live switch happens on
  `EMAIL_PROVIDER=resend` + a non-empty `RESEND_API_KEY`; with the key blank
  the provider records `status=outbox` and makes NO network call, so nothing
  errors while the secret is unfilled. Non-2xx is captured as
  `status=failed` with the Resend error body preserved — the send never
  raises into OTP/invite/follow-up flows. This covers all three email kinds
  (login_code, invite, follow_up) since they all route through `send_email`.
  New `tests/test_email_resend.py` (4 cases: exact request shape + id capture,
  403 resend.dev restriction recorded as failed, blank key = outbox-only with
  no network, retired-pipe guard). Full suite: **70 passed** serial.
  **KNOWN LIMIT**: `onboarding@resend.dev` can only deliver to the Resend
  account owner's own address — any other recipient gets HTTP 403. A verified
  domain in Resend is required before real client follow-ups can land.
- **2026-09-24 Twilio sandbox number changed**: `ORG_WHATSAPP_FROM` moved from
  `whatsapp:+14155238886` to `whatsapp:+17372508034` in `backend/.env` and
  `.env.example`; backend restarted and `settings.ORG_WHATSAPP_FROM` verified
  live. Webhook URLs are UNCHANGED (the sender number is not part of them):
  inbound `POST {APP_URL}/api/webhooks/twilio-whatsapp/inbound`, status
  callback `POST {APP_URL}/api/webhooks/twilio-whatsapp/status`. Verified on
  preview: unsigned POST → 403 on both; correctly signed POST (signature
  computed over the exact `APP_URL` + path) → 200 on both, so the
  `X-Forwarded-Host` URL-reconstruction still matches what Twilio signs.
  Note: the sandbox number is NOT in `IncomingPhoneNumbers` (expected — the
  sandbox sender is not a purchased number), and each recipient must re-send
  the sandbox join phrase to the NEW number; old joins do not carry over.
- **2026-09-24 Conversation shows email (only item taken from that batch)**:
  `GET /api/app/hubs/{id}/conversation` now returns `email_to` (the
  snapshotted `contact_email`) + `email_status` on every Dueo `follow_up`
  entry; client `reply` rows carry neither. `HubDetail.jsx` annotates the
  SAME bubble (no duplicate email rows) with "Also emailed to x@y ·
  delivered / email failed / pending" (`data-testid="msg-{i}-email"`),
  applied to message 1 (approve-time) and the scheduled 2-5 alike. System
  emails (OTP/invite) are deliberately NOT shown. New test
  `test_hub_conversation_exposes_email_fallback_state`. Full suite: **66
  passed** serial. Verified live on preview with a seeded hub — screenshot
  shows one "delivered" and one "email failed" annotation.
  Retry, Production Sender and Contact Change Warning remain deliberately
  skipped per user decision (not oversights).
- **2026-09-24 Email fallback shipped**: every WhatsApp send from `approve_plan`
  and `dispatch_due` now fires an INDEPENDENT email to the snapshotted
  `contact_email` via the existing `providers.email.send_email` pipe (kind=
  `follow_up`). Same body, wrapped in a minimal `<table>` HTML shell with
  `white-space:pre-wrap` so it reads identically to WhatsApp. Email failures
  are caught + logged and NEVER fail the WA row — the row records
  `email_status` / `email_provider_id` for observability. Subject-per-category:
  "Invoice X — payment link inside" / "Reminder: invoice X" / "Overdue:
  invoice X". Rows with no contact_email skip the email path entirely. Even
  today with `EMERGENT_EMAIL_KEY=401`, every send lands in `emails_outbox`
  with `status=failed` so the flow is provable; once the key is rotated,
  every new approve/dispatch auto-delivers.
  New tests `test_email_fallback.py` (3 cases: email fires on every dispatch,
  email failure leaves WA success intact, no-email-on-row is skipped). Full
  suite: **65 passed** serial. **Retry** (backoff on failed rows) and
  **Contact Change Warning** intentionally SKIPPED — atomic claim + snapshot
  already cover the correctness gaps; retry is a real gap (transient Twilio
  5xx parks the row at `failed` forever) but user paused it, contact-change
  warning is purely UX awareness (snapshot already makes it safe).
- **2026-09-24 Scheduler Tick + Mark-as-Paid shipped**: new
  `services/follow_ups.py` owns both scheduling (`build_scheduled_rows`) and
  dispatch (`dispatch_due`). On approve, the initial POC message is sent
  immediately AND rows 2-5 are persisted with `status=scheduled` — cadence
  is day 3/7/14/30 after `due_date` at 09:00 UTC, POC on 2 & 3, escalation_1
  on 4 & 5 (fallback to POC follow_up when no esc_1). Every scheduled row
  carries a full `contact_name/phone/email` snapshot from approve time, so
  the confirmed replace-semantics on `payment_hub_contacts` cannot rewrite
  future sends (SECTION-8 warn/re-approve UI still pending). The
  APScheduler `scheduler_tick` (every minute, existing infra) now calls
  `dispatch_due`, which uses `store.claim_scheduled_follow_up` (atomic
  find_one_and_update flipping `scheduled → dispatching`) so racing workers
  cannot double-send. Paid/disputed hubs are recorded as `skipped` with a
  `skip_reason` so nothing silently vanishes. Send failures land as
  `status=failed` with the error preserved — no retry yet (backlog).
  New endpoint `POST /api/hubs/{id}/mark-paid` (auth, tenant-scoped, 404
  cross-org) flips the hub to `status=paid` + records `paid_at/paid_by`,
  cancels every still-scheduled follow-up via
  `store.cancel_scheduled_follow_ups` (already-sent rows untouched),
  idempotent (2nd call returns `already_paid=true` with 0 canceled). Frontend
  `HubDetail.jsx` shows a mint "Mark as paid" button with confirm dialog,
  swaps to a "Paid on YYYY-MM-DD" badge post-flip; `data-testid`
  `mark-paid-btn` / `mark-paid-badge` / `mark-paid-err`. New tests:
  `test_scheduler_dispatch.py` (5 cases: cadence + snapshot, ready-window
  filter, paid-hub skip, per-row failure isolation, atomic-claim uniqueness);
  `test_mark_paid.py` (4 cases: flip + cancel, idempotency, already-sent
  untouched, cross-org 404). Live E2E curl: seeded hub with 2 scheduled →
  POST /mark-paid → 200 `{status:paid, canceled:2}` → dashboard
  `paid_this_month=1` → 2nd POST returns `already_paid=true, canceled=0` →
  scheduled rows now `canceled` with reason `marked_paid`.
  Full suite: **62 passed** serial. Production sender + Section-8 contact-
  change warn-on-approve remain in backlog per user hold.
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
