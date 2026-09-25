"""Live webhook tests against the preview URL for the reverted +14155238886 sandbox."""
import os
import time
import uuid

import pytest
import requests
from twilio.request_validator import RequestValidator
from pymongo import MongoClient

BASE_URL = "https://invoice-follow-up-8.preview.emergentagent.com"
INBOUND = f"{BASE_URL}/api/webhooks/twilio-whatsapp/inbound"
STATUS = f"{BASE_URL}/api/webhooks/twilio-whatsapp/status"


def _load_env():
    env = {}
    with open("/app/backend/.env") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k] = v.strip().strip('"').strip("'")
    return env


ENV = _load_env()
AUTH_TOKEN = ENV["TWILIO_AUTH_TOKEN"]
MONGO_URL = ENV["MONGO_URL"]
DB_NAME = ENV["DB_NAME"]


@pytest.fixture(scope="module")
def db():
    client = MongoClient(MONGO_URL)
    return client[DB_NAME]


def _sign(url, form):
    return RequestValidator(AUTH_TOKEN).compute_signature(url, form)


def test_inbound_unsigned_403():
    r = requests.post(INBOUND, data={"MessageSid": "SMx", "From": "whatsapp:+916300886029",
                                      "To": "whatsapp:+14155238886", "Body": "hi"}, timeout=15)
    assert r.status_code == 403, r.text
    assert "invalid_twilio_signature" in r.text or "invalid" in r.text.lower()


def test_inbound_signed_200_and_persist(db):
    sid = f"SM_test_{uuid.uuid4().hex[:16]}"
    form = {
        "MessageSid": sid,
        "From": "whatsapp:+916300886029",
        "To": "whatsapp:+14155238886",
        "Body": "hello from test",
    }
    sig = _sign(INBOUND, form)
    r = requests.post(INBOUND, data=form, headers={"X-Twilio-Signature": sig}, timeout=15)
    assert r.status_code == 200, r.text
    # empty TwiML
    body = r.text.strip()
    assert body == "" or "<Response" in body
    time.sleep(0.5)
    rows = list(db.whatsapp_messages.find({"provider_sid": sid}))
    if not rows:
        rows = list(db.whatsapp_messages.find({"_id": sid}))
    assert len(rows) == 1, f"expected 1 row for {sid}, got {len(rows)}"
    row = rows[0]
    assert row.get("direction") == "inbound"


def test_inbound_idempotent(db):
    sid = f"SM_idem_{uuid.uuid4().hex[:16]}"
    form = {
        "MessageSid": sid,
        "From": "whatsapp:+916300886029",
        "To": "whatsapp:+14155238886",
        "Body": "dup",
    }
    sig = _sign(INBOUND, form)
    headers = {"X-Twilio-Signature": sig}
    r1 = requests.post(INBOUND, data=form, headers=headers, timeout=15)
    r2 = requests.post(INBOUND, data=form, headers=headers, timeout=15)
    assert r1.status_code == 200 and r2.status_code == 200
    time.sleep(0.5)
    q = {"$or": [{"provider_sid": sid}, {"_id": sid}]}
    rows = list(db.whatsapp_messages.find(q))
    assert len(rows) == 1, f"idempotency violated: {len(rows)} rows"


def test_status_unsigned_403():
    r = requests.post(STATUS, data={"MessageSid": "SMx", "MessageStatus": "delivered"}, timeout=15)
    assert r.status_code == 403


def test_status_signed_updates_row(db):
    # Seed an inbound-like row via signed inbound first, then post signed status.
    sid = f"SM_stat_{uuid.uuid4().hex[:16]}"
    inbound_form = {
        "MessageSid": sid,
        "From": "whatsapp:+916300886029",
        "To": "whatsapp:+14155238886",
        "Body": "seed",
    }
    sig_in = _sign(INBOUND, inbound_form)
    r_in = requests.post(INBOUND, data=inbound_form, headers={"X-Twilio-Signature": sig_in}, timeout=15)
    assert r_in.status_code == 200

    status_form = {"MessageSid": sid, "MessageStatus": "delivered"}
    sig_st = _sign(STATUS, status_form)
    r_st = requests.post(STATUS, data=status_form, headers={"X-Twilio-Signature": sig_st}, timeout=15)
    assert r_st.status_code == 200, r_st.text
    time.sleep(0.5)
    q = {"$or": [{"provider_sid": sid}, {"_id": sid}]}
    row = db.whatsapp_messages.find_one(q)
    assert row is not None
    assert row.get("status") == "delivered", f"status not updated: {row.get('status')}"
