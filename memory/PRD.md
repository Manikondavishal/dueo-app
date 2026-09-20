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
- P1: Phase 2 — invoice upload + LLM field extraction into invoices collection; setup steps 2–3.
- P1: follow-up plan engine + email sending via the scheduler tick pipeline (already atomic-claim ready).
- P2: WhatsApp channel, Razorpay/Stripe payment page, Shield/MSMED, Proof of promise document.

## Deployment
- Env vars in `backend/.env` (+ `.env.example` mirror). GitHub Save + Deploy are user-triggered via the UI.
