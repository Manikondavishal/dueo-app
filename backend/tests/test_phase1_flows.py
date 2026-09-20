"""Phase 1 end-to-end backend tests: invite request, admin guard, OTP login,
invite-consume, setup, suspend revocation."""
import os
import re
import time
import uuid

import pytest
import requests
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") if os.environ.get("REACT_APP_BACKEND_URL") else "https://invoice-follow-up-8.preview.emergentagent.com"
ORIGIN = BASE_URL
ADMIN_EMAIL = "vishalmanikonda@icloud.com"
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]


def _headers(ip: str | None = None):
    h = {"Content-Type": "application/json", "Origin": ORIGIN}
    if ip:
        h["X-Forwarded-For"] = ip
    else:
        # Unique per call to avoid cross-test rate limits
        h["X-Forwarded-For"] = f"198.51.100.{uuid.uuid4().int % 250 + 1}"
    return h


@pytest.fixture(scope="session")
def db():
    client = MongoClient(MONGO_URL)
    d = client[DB_NAME]
    # Ensure rate limits for admin email/IP won't block our OTP requests across reruns
    d.rate_limits.delete_many({"kind": {"$in": ["otp_email", "otp_ip", "verify_ip"]}})
    d.auth_otps.delete_many({"email": ADMIN_EMAIL})
    return d


def _get_latest_email(db, to: str, kind: str):
    return db.emails_outbox.find_one({"to": to, "kind": kind}, sort=[("created_at", -1)])


def _admin_login(db) -> requests.Session:
    """Fresh admin login: request code, extract from LATEST outbox entry sent AFTER request."""
    import time as _t
    before = db.emails_outbox.count_documents({"to": ADMIN_EMAIL, "kind": "login_code"})
    requests.post(f"{BASE_URL}/api/auth/request-code",
                  json={"email": ADMIN_EMAIL}, headers=_headers(), timeout=10)
    # Wait for the new email to land
    for _ in range(20):
        after = db.emails_outbox.count_documents({"to": ADMIN_EMAIL, "kind": "login_code"})
        if after > before:
            break
        _t.sleep(0.05)
    email = _get_latest_email(db, ADMIN_EMAIL, "login_code")
    code = re.search(r"<strong>(\d{6})</strong>", email["html"]).group(1)
    s = requests.Session()
    v = s.post(f"{BASE_URL}/api/auth/verify",
               json={"email": ADMIN_EMAIL, "code": code}, headers=_headers(), timeout=10)
    assert v.status_code == 200, v.text
    return s


# ------------------------------ health ------------------------------
def test_health():
    r = requests.get(f"{BASE_URL}/api/health", timeout=10)
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


# ------------------------------ invite/request ------------------------------
CONFIRM = "Thanks for requesting an invite. We review every request by hand."


def _lead_body(email, btype="agency_studio", website=""):
    return {
        "full_name": "Test User",
        "business_name": "Test Biz",
        "work_email": email,
        "mobile": "+919999999901",
        "business_type": btype,
        "city_state": "Bengaluru, KA",
        "monthly_invoice_volume": "10-50",
        "udyam_number": None,
        "company_website": website,
    }


def test_invite_request_known_type_creates_new_lead(db):
    email = f"test_{uuid.uuid4().hex[:8]}@example.com"
    r = requests.post(f"{BASE_URL}/api/invite/request", json=_lead_body(email, "consulting"),
                      headers=_headers(), timeout=10)
    assert r.status_code == 200
    assert r.json()["message"] == CONFIRM
    lead = db.waitlist_leads.find_one({"work_email": email})
    assert lead is not None
    assert lead["status"] == "new"
    assert lead["business_type"] == "consulting"


def test_invite_request_other_type_manual_review(db):
    email = f"test_{uuid.uuid4().hex[:8]}@example.com"
    r = requests.post(f"{BASE_URL}/api/invite/request", json=_lead_body(email, "other"),
                      headers=_headers(), timeout=10)
    assert r.status_code == 200
    lead = db.waitlist_leads.find_one({"work_email": email})
    assert lead["status"] == "manual_review"


def test_invite_request_idempotent_same_email(db):
    email = f"test_{uuid.uuid4().hex[:8]}@example.com"
    r1 = requests.post(f"{BASE_URL}/api/invite/request", json=_lead_body(email),
                       headers=_headers(), timeout=10)
    r2 = requests.post(f"{BASE_URL}/api/invite/request", json=_lead_body(email),
                       headers=_headers(), timeout=10)
    assert r1.status_code == 200 and r2.status_code == 200
    assert r1.json() == r2.json()
    count = db.waitlist_leads.count_documents({"work_email": email})
    assert count == 1


def test_invite_request_honeypot_stores_nothing(db):
    email = f"test_{uuid.uuid4().hex[:8]}@example.com"
    r = requests.post(f"{BASE_URL}/api/invite/request",
                      json=_lead_body(email, website="http://spam.com"),
                      headers=_headers(), timeout=10)
    assert r.status_code == 200
    assert r.json()["message"] == CONFIRM
    lead = db.waitlist_leads.find_one({"work_email": email})
    assert lead is None


def test_invite_request_rate_limited(db):
    # Reset the invite_ip counter so this is deterministic on a shared backend.
    db.rate_limits.delete_many({"kind": "invite_ip"})
    ip = f"203.0.113.{int(time.time()) % 250 + 1}"
    hdrs = {**_headers(), "X-Forwarded-For": ip}
    codes = []
    for i in range(6):
        email = f"rl_{uuid.uuid4().hex[:8]}@example.com"
        codes.append(requests.post(f"{BASE_URL}/api/invite/request", json=_lead_body(email),
                                   headers=hdrs, timeout=10).status_code)
    assert 429 in codes, f"expected a 429 within 6 requests, got {codes}"


# ------------------------------ admin guard ------------------------------
def test_admin_guard_401_without_session():
    r = requests.get(f"{BASE_URL}/api/admin/leads", timeout=10)
    assert r.status_code == 401


# ------------------------------ request-code neutrality ------------------------------
def test_request_code_neutral_known_and_unknown():
    r_known = requests.post(f"{BASE_URL}/api/auth/request-code",
                            json={"email": ADMIN_EMAIL}, headers=_headers(), timeout=10)
    r_unknown = requests.post(f"{BASE_URL}/api/auth/request-code",
                              json={"email": f"nobody_{uuid.uuid4().hex}@example.com"},
                              headers=_headers(), timeout=10)
    assert r_known.status_code == 200 and r_unknown.status_code == 200
    assert r_known.json() == r_unknown.json()
    assert "sent a sign-in code" in r_known.json()["message"]


# ------------------------------ admin OTP full login ------------------------------
def test_admin_login_flow(db):
    # Request code
    r = requests.post(f"{BASE_URL}/api/auth/request-code",
                      json={"email": ADMIN_EMAIL}, headers=_headers(), timeout=10)
    assert r.status_code == 200
    # Fetch code from outbox
    email = _get_latest_email(db, ADMIN_EMAIL, "login_code")
    assert email is not None
    m = re.search(r"<strong>(\d{6})</strong>", email["html"])
    assert m, f"code not found in html: {email['html'][:200]}"
    code = m.group(1)
    # Verify
    s = requests.Session()
    r2 = s.post(f"{BASE_URL}/api/auth/verify",
                json={"email": ADMIN_EMAIL, "code": code}, headers=_headers(), timeout=10)
    assert r2.status_code == 200, r2.text
    assert r2.json()["ok"] is True
    assert "dueo_session" in s.cookies.get_dict()
    # Admin GET /api/admin/leads should now work
    r3 = s.get(f"{BASE_URL}/api/admin/leads", timeout=10)
    assert r3.status_code == 200
    assert "leads" in r3.json()


# ------------------------------ full invite consume + setup + suspend ------------------------------
def test_full_invite_consume_setup_and_suspend(db):
    # 1) Create fresh lead
    lead_email = f"newowner_{uuid.uuid4().hex[:8]}@example.com"
    r = requests.post(f"{BASE_URL}/api/invite/request",
                      json=_lead_body(lead_email, "agency_studio"),
                      headers=_headers(), timeout=10)
    assert r.status_code == 200
    lead = db.waitlist_leads.find_one({"work_email": lead_email})

    # 2) Log in as admin
    admin_s = _admin_login(db)

    # 3) Approve the lead
    r_ap = admin_s.post(f"{BASE_URL}/api/admin/leads/{lead['id']}/action",
                        json={"action": "approve"}, headers=_headers(), timeout=10)
    assert r_ap.status_code == 200, r_ap.text

    # 4) Read invite token from outbox
    invite_email = _get_latest_email(db, lead_email, "invite")
    assert invite_email
    tok_m = re.search(r"/invite\?token=([^\"<]+)", invite_email["html"])
    assert tok_m, invite_email["html"][:400]
    token = tok_m.group(1)

    # 5) Consume invite
    user_s = requests.Session()
    r_c = user_s.post(f"{BASE_URL}/api/auth/invite/consume",
                      json={"token": token}, headers=_headers(), timeout=10)
    assert r_c.status_code == 200, r_c.text
    body = r_c.json()
    assert body["ok"] is True
    assert body["user"]["email"] == lead_email
    assert body["org"]["display_name"] == "Test Biz"
    assert "dueo_session" in user_s.cookies.get_dict()

    # 6) Reusing the same token returns 400 with neutral message
    r_reuse = requests.post(f"{BASE_URL}/api/auth/invite/consume",
                            json={"token": token}, headers=_headers(), timeout=10)
    assert r_reuse.status_code == 400
    assert "can't be used" in r_reuse.json()["detail"]

    # 7) Setup: consent=false rejected
    r_s0 = user_s.post(f"{BASE_URL}/api/app/setup",
                       json={"display_name": "Test Biz Studio", "mobile": "+919999999911",
                             "consent": False, "consent_version": "2026-06-01"},
                       headers=_headers(), timeout=10)
    assert r_s0.status_code == 400

    # 8) Setup: consent=true succeeds and setup_completed=true
    r_s = user_s.post(f"{BASE_URL}/api/app/setup",
                      json={"display_name": "Test Biz Studio", "mobile": "+919999999911",
                            "consent": True, "consent_version": "2026-06-01"},
                      headers=_headers(), timeout=10)
    assert r_s.status_code == 200, r_s.text
    org = r_s.json()["org"]
    assert org["settings"]["setup_completed"] is True

    # 9) /api/auth/me before suspend -> authenticated=true
    me_before = user_s.get(f"{BASE_URL}/api/auth/me", timeout=10)
    assert me_before.json()["authenticated"] is True

    # 10) Admin suspends user, then /me returns authenticated=false
    user_id = body["user"]["id"]
    r_susp = admin_s.post(f"{BASE_URL}/api/admin/users/{user_id}/suspend",
                          headers=_headers(), timeout=10)
    assert r_susp.status_code == 200, r_susp.text
    me_after = user_s.get(f"{BASE_URL}/api/auth/me", timeout=10)
    assert me_after.json()["authenticated"] is False


# ------------------------------ invalid invite ------------------------------
def test_consume_invalid_token():
    r = requests.post(f"{BASE_URL}/api/auth/invite/consume",
                      json={"token": "totally_bogus_token_xyz"},
                      headers=_headers(), timeout=10)
    assert r.status_code == 400
    assert "can't be used" in r.json()["detail"]
