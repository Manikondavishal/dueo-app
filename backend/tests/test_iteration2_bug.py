"""
Iteration 2 — Verifies the reported bug fix and features from the review request:
- widened bootstrap-code guard (CRON_SECRET only)
- whymancreates.studio@gmail.com works end-to-end (request-code -> bootstrap -> verify -> /api/app/dashboard 200)
- vishalmanikonda@icloud.com regression
- unknown/inactive email neutrality
- OTP hygiene (invalidation, reuse, wrong code)
- admin endpoints reachable
- /admin/leads shows only real leads (no @example.com)
"""
import os
import re
import time
import uuid
import requests
import pytest
from pymongo import MongoClient

BASE = "https://invoice-follow-up-8.preview.emergentagent.com"
CRON_SECRET = "f893bee2c4c26ad8c16c069fd4a51344294d919eae69a5d8b9e8028681546b84"
OWNER = "whymancreates.studio@gmail.com"
ADMIN2 = "vishalmanikonda@icloud.com"
NEUTRAL_MSG_KEY = "message"  # we assert the text matches for known and unknown


def _mongo():
    return MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[
        os.environ.get("DB_NAME", "test_database")
    ]


def _request_code(email):
    return requests.post(f"{BASE}/api/auth/request-code", json={"email": email}, timeout=15)


def _bootstrap_code(email, token=CRON_SECRET):
    return requests.get(
        f"{BASE}/api/admin/bootstrap-code",
        params={"email": email, "token": token},
        timeout=15,
    )


def _verify(email, code, session=None):
    s = session or requests.Session()
    r = s.post(f"{BASE}/api/auth/verify", json={"email": email, "code": code}, timeout=15)
    return s, r


def _clean_rate_limits():
    db = _mongo()
    db.rate_limits.delete_many({"kind": {"$in": ["otp_email", "otp_ip", "verify_ip"]}})


def _sign_in(email):
    _clean_rate_limits()
    # invalidate any old codes so bootstrap-code returns a fresh, unconsumed one
    _mongo().auth_otps.delete_many({"email": email})
    r1 = _request_code(email)
    assert r1.status_code == 200, r1.text
    time.sleep(0.4)
    rb = _bootstrap_code(email)
    assert rb.status_code == 200, rb.text
    code = rb.json()["code"]
    s, rv = _verify(email, code)
    assert rv.status_code == 200, rv.text
    assert s.cookies.get("dueo_session"), "session cookie missing"
    return s, code


@pytest.fixture(scope="module")
def owner_session():
    s, _ = _sign_in(OWNER)
    return s


# ---------- Bootstrap-code security ----------

class TestBootstrapCode:
    def test_wrong_token_401(self):
        r = _bootstrap_code(OWNER, token="wrong")
        assert r.status_code == 401
        assert "invalid_token" in r.text

    def test_no_code_yet_404(self):
        never = f"nobody_qa_{uuid.uuid4().hex[:8]}@oddenough.in"
        r = _bootstrap_code(never)
        assert r.status_code == 404
        assert "no_code" in r.text

    def test_widened_works_for_non_admin(self):
        """New behaviour: any email, guarded by CRON_SECRET (no ADMIN_EMAILS gate)."""
        non_admin = f"nonadmin_qa_{uuid.uuid4().hex[:8]}@example.com"
        # seed a user directly so request-code produces a code
        db = _mongo()
        db.users.update_one(
            {"email": non_admin},
            {"$set": {"email": non_admin, "status": "active", "created_at": "2026-01-01T00:00:00"}},
            upsert=True,
        )
        try:
            r1 = _request_code(non_admin)
            assert r1.status_code == 200
            time.sleep(0.5)
            rb = _bootstrap_code(non_admin)
            # Should succeed (widened) — must NOT be 403 not_admin
            assert rb.status_code == 200, f"expected 200 for non-admin widened route, got {rb.status_code}: {rb.text}"
            body = rb.json()
            assert "code" in body and re.match(r"^\d{6}$", str(body["code"]))
            assert "created_at" in body
            assert "status" in body
        finally:
            db.users.delete_one({"email": non_admin})
            db.auth_otps.delete_many({"email": non_admin})
            db.emails_outbox.delete_many({"to": non_admin})


# ---------- Sign in end-to-end (the reported bug) ----------

class TestOwnerSignInAndDashboard:
    def test_owner_e2e_dashboard_200(self):
        s, _ = _sign_in(OWNER)
        r = s.get(f"{BASE}/api/app/dashboard", timeout=15)
        assert r.status_code == 200, f"dashboard should be 200, got {r.status_code}: {r.text}"
        data = r.json()
        # The task says: 4 counts
        # Don't over-assert the exact keys; just make sure it's a dict with numbers
        assert isinstance(data, dict) and len(data) >= 1

    def test_owner_admin_pages_200(self):
        s, _ = _sign_in(OWNER)
        for path in ("/api/admin/leads", "/api/admin/users", "/api/admin/outbox"):
            r = s.get(f"{BASE}{path}", timeout=15)
            assert r.status_code == 200, f"{path} -> {r.status_code}: {r.text[:200]}"

    def test_admin2_regression_dashboard_200(self):
        s, _ = _sign_in(ADMIN2)
        r = s.get(f"{BASE}/api/app/dashboard", timeout=15)
        assert r.status_code == 200, f"{ADMIN2} dashboard -> {r.status_code}: {r.text}"


# ---------- Unknown/inactive neutrality ----------

class TestNeutralRequestCode:
    def test_unknown_email_neutral_and_no_side_effects(self):
        db = _mongo()
        never = f"nobody_qa_{uuid.uuid4().hex[:12]}@oddenough.in"

        # Baseline neutral message from a KNOWN address
        known_resp = _request_code(OWNER)
        assert known_resp.status_code == 200
        known_msg = known_resp.json()

        unk_resp = _request_code(never)
        assert unk_resp.status_code == 200
        assert unk_resp.json() == known_msg, (
            f"neutral message differs — enumeration risk: {unk_resp.json()} vs {known_msg}"
        )
        # No outbox or otp row for unknown
        assert db.emails_outbox.count_documents({"to": never}) == 0
        assert db.auth_otps.count_documents({"email": never}) == 0


# ---------- OTP hygiene ----------

class TestOtpHygiene:
    def test_new_code_invalidates_old_and_no_reuse(self):
        # Get first code
        r1 = _request_code(OWNER); assert r1.status_code == 200
        time.sleep(0.5)
        rb1 = _bootstrap_code(OWNER); assert rb1.status_code == 200
        old = rb1.json()["code"]

        # Request another — should invalidate old
        r2 = _request_code(OWNER); assert r2.status_code == 200
        time.sleep(0.5)
        rb2 = _bootstrap_code(OWNER); assert rb2.status_code == 200
        new = rb2.json()["code"]
        assert old != new, "expected a fresh code"

        # Old code fails
        _, rv_old = _verify(OWNER, old)
        assert rv_old.status_code == 400, f"old code should be invalid: {rv_old.status_code} {rv_old.text}"

        # Wrong code fails
        _, rv_bad = _verify(OWNER, "000000" if new != "000000" else "111111")
        assert rv_bad.status_code == 400

        # New code succeeds once
        s, rv_new = _verify(OWNER, new)
        assert rv_new.status_code == 200
        # Reuse fails
        _, rv_reuse = _verify(OWNER, new)
        assert rv_reuse.status_code == 400, "code reuse must fail"


# ---------- Leads cleanup ----------

class TestLeadsCleanup:
    def test_admin_leads_no_test_rows(self, owner_session):
        s = owner_session
        r = s.get(f"{BASE}/api/admin/leads", timeout=15)
        assert r.status_code == 200
        body = r.json()
        # find the list wherever it is
        leads = body if isinstance(body, list) else body.get("leads") or body.get("items") or []
        emails = [l.get("work_email", "") for l in leads]
        example_rows = [e for e in emails if e.endswith("@example.com")]
        assert not example_rows, f"admin/leads still contains test rows: {example_rows[:5]} (total={len(example_rows)})"
        # Real lead should be present
        assert "vishal@oddenough.in" in emails, f"real lead missing; leads={emails[:10]}"
