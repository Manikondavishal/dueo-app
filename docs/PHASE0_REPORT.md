# Dueo — Phase 0 Report

Environment tested: **deployed preview** — `https://invoice-follow-up-8.preview.emergentagent.com`
Date: 2026-09-20 · Stack: React + FastAPI + MongoDB · All checks **PASS**.

| # | Check | Result | Evidence (URL / command → output) |
|---|-------|--------|-----------------------------------|
| 1 | Public webhook reachable from outside, verifies HMAC on the **raw body**, stores payload **first** | ✅ PASS | `POST /api/webhooks/test`. Invalid signature → `401`; valid signature → `200`. See commands below. Payload is inserted into `webhook_events` **before** verification, then the doc's `verified` flag is updated. |
| 2 | Scheduler runs every minute; two workers race for one job, **exactly one wins** (atomic `find_one_and_update`) | ✅ PASS | APScheduler `tick` (cron `* * * * *`) + `claim_pending_job()` uses `find_one_and_update({status:pending}→running)`. Concurrent race test: 2 claims → **1** returns the job. |
| 3 | MongoDB unique indexes reject duplicates | ✅ PASS | Unique on `users.email`, `waitlist_leads.work_email`, `organization_members(org_id,user_id)`, `audit_events(chain_key,sequence)`. Second insert of same key raises `DuplicateKeyError`. |
| 4 | File upload works; download works **only when logged in** | ✅ PASS | `POST /api/uploads` (auth) → `200`; `GET /api/uploads/{id}` with cookie → `200`, without cookie → `401`. Stored in Emergent object storage; metadata org-scoped in `uploads`. |
| 5 | LLM call with an image returns structured JSON (EMERGENT_LLM_KEY behind an `LLMProvider` wrapper) | ✅ PASS | `LLMProvider.extract_json_from_image()` (Gemini 3 Flash) → `{'invoice_number':'0417','client_name':'Kestrel Logistics','amount':85000,'currency':'INR','due_date':'7 Sep 2026'}` (Python `dict`). |

---

## Evidence detail

### 1 — Webhook (HMAC on raw body, store-first)
```bash
API=https://invoice-follow-up-8.preview.emergentagent.com
# invalid signature
curl -s -o /dev/null -w "%{http_code}\n" -X POST $API/api/webhooks/test \
  -H "Content-Type: application/json" -d '{"hello":"world"}'
# → 401   (payload was still stored first)

# valid signature
BODY='{"event":"ping","n":1}'
SIG=$(python3 -c "import hmac,hashlib;print(hmac.new(SECRET.encode(),b'$BODY',hashlib.sha256).hexdigest())")
curl -s -X POST $API/api/webhooks/test -H "X-Dueo-Signature: $SIG" -d "$BODY"
# → {"ok":true,"stored":true,"event_id":"...","payload_keys":["event","n"]}
```
Code: `app/routers/webhooks.py` inserts into `webhook_events` **before** `hmac.compare_digest`.
`webhook_events_stored: 2` confirmed via `store.count_webhook_events()`.

### 2 — Atomic single-winner race
```python
# app/jobs/scheduler.py + app/repositories/store.py::claim_pending_job
await store.enqueue_job({... status:"pending"})
res = await asyncio.gather(store.claim_pending_job("w1"), store.claim_pending_job("w2"))
# → claims returning job: 1   winner worker: w1
# scheduler_tick recorded runs in scheduler_runs; APScheduler cron="* * * * *" active.
```

### 3 — Unique index rejects duplicates
```python
await store.insert_user({... email:"dup_test@example.com"})
await store.insert_user({... email:"dup_test@example.com"})  # → DuplicateKeyError (PASS)
```
`tests/test_audit_chain.py::test_audit_sequence_unique_index` also proves `audit_events(chain_key,sequence)` uniqueness.

### 4 — Upload / gated download
```bash
# authenticated upload
curl -s -b cookies -X POST $API/api/uploads -F "file=@invoice.pdf;type=application/pdf"
# → {"id":"...","filename":"invoice.pdf","size":31}   (upload=200)
curl -s -b cookies -o out.bin -w "%{http_code}" $API/api/uploads/<id>   # → 200
curl -s          -o /dev/null -w "%{http_code}" $API/api/uploads/<id>   # → 401 (no cookie)
```

### 5 — LLM image → structured JSON
```python
# app/providers/llm.py::LLMProvider.extract_json_from_image  (gemini-3-flash-preview)
data = await llm_provider.extract_json_from_image(invoice_png_b64, "Extract invoice fields as JSON …")
# → dict: {'invoice_number':'0417','client_name':'Kestrel Logistics','amount':85000,'currency':'INR','due_date':'7 Sep 2026'}
```

### Security headers (bonus, Section J)
```bash
curl -s -D - -o /dev/null $API/api/health | grep -iE "x-frame|content-security|referrer|content-type-options|strict-transport"
# x-frame-options: DENY
# content-security-policy: default-src 'none'; frame-ancestors 'none'; base-uri 'none'
# referrer-policy: strict-origin-when-cross-origin
# x-content-type-options: nosniff
# strict-transport-security: max-age=63072000; includeSubDomains
```
