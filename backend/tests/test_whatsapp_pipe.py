"""Tests for the Twilio WhatsApp pipe (P4) and Section-1 data model."""
import httpx
import pytest
import pytest_asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from twilio.request_validator import RequestValidator

from app.config import settings  # noqa: E402

API = settings.APP_URL.rstrip("/") + "/api"
TWILIO_AUTH_TOKEN = settings.TWILIO_AUTH_TOKEN


def _sign(url: str, form: dict) -> str:
    return RequestValidator(TWILIO_AUTH_TOKEN).compute_signature(url, form)


@pytest_asyncio.fixture(autouse=True)
async def _clean_hub_collections():
    """Wipe Section-1 collections between tests so assertions stay deterministic."""
    client = AsyncIOMotorClient(settings.MONGO_URL)
    db = client[settings.DB_NAME]
    for c in ("whatsapp_messages", "payment_hubs", "payment_hub_contacts",
              "follow_up_plans", "follow_up_messages"):
        await db[c].delete_many({})
    yield
    client.close()


@pytest.mark.asyncio
async def test_whatsapp_inbound_rejects_bad_signature():
    url = f"{API}/webhooks/twilio-whatsapp/inbound"
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.post(url, data={"MessageSid": "SM1", "From": "whatsapp:+1", "Body": "hi"},
                         headers={"X-Twilio-Signature": "not-a-real-signature"})
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_whatsapp_inbound_accepts_valid_signature_and_persists():
    url = f"{API}/webhooks/twilio-whatsapp/inbound"
    form = {"MessageSid": "SM_valid_1", "From": "whatsapp:+15551234567",
            "To": "whatsapp:+17372508034", "Body": "hey there", "NumMedia": "0"}
    sig = _sign(url, form)
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.post(url, data=form, headers={"X-Twilio-Signature": sig})
    assert r.status_code == 200
    assert "<Response>" in r.text

    client = AsyncIOMotorClient(settings.MONGO_URL)
    db = client[settings.DB_NAME]
    doc = await db.whatsapp_messages.find_one({"provider_sid": "SM_valid_1"})
    assert doc is not None
    assert doc["direction"] == "inbound"
    assert doc["body"] == "hey there"
    client.close()


@pytest.mark.asyncio
async def test_whatsapp_inbound_is_idempotent_under_retries():
    url = f"{API}/webhooks/twilio-whatsapp/inbound"
    form = {"MessageSid": "SM_dup_1", "From": "whatsapp:+15551234567",
            "To": "whatsapp:+17372508034", "Body": "one", "NumMedia": "0"}
    sig = _sign(url, form)
    async with httpx.AsyncClient(timeout=15) as c:
        r1 = await c.post(url, data=form, headers={"X-Twilio-Signature": sig})
        # retry with same SID + a different body — the first write must win.
        form2 = {**form, "Body": "two"}
        sig2 = _sign(url, form2)
        r2 = await c.post(url, data=form2, headers={"X-Twilio-Signature": sig2})
    assert r1.status_code == 200
    assert r2.status_code == 200

    client = AsyncIOMotorClient(settings.MONGO_URL)
    db = client[settings.DB_NAME]
    docs = await db.whatsapp_messages.find({"provider_sid": "SM_dup_1"}).to_list(5)
    assert len(docs) == 1
    assert docs[0]["body"] == "one"
    client.close()


@pytest.mark.asyncio
async def test_whatsapp_status_callback_updates_row():
    url_in = f"{API}/webhooks/twilio-whatsapp/inbound"
    form_in = {"MessageSid": "SM_status_1", "From": "whatsapp:+15551234567",
               "To": "whatsapp:+17372508034", "Body": "hi", "NumMedia": "0"}
    async with httpx.AsyncClient(timeout=15) as c:
        await c.post(url_in, data=form_in, headers={"X-Twilio-Signature": _sign(url_in, form_in)})

        url_st = f"{API}/webhooks/twilio-whatsapp/status"
        form_st = {"MessageSid": "SM_status_1", "MessageStatus": "delivered"}
        await c.post(url_st, data=form_st, headers={"X-Twilio-Signature": _sign(url_st, form_st)})

    client = AsyncIOMotorClient(settings.MONGO_URL)
    db = client[settings.DB_NAME]
    doc = await db.whatsapp_messages.find_one({"provider_sid": "SM_status_1"})
    assert doc["status"] == "delivered"
    client.close()


@pytest.mark.asyncio
async def test_section1_collections_round_trip():
    """Insert a payment hub + contact + plan + follow-up message via the store
    and read them back — exercises indexes + document shape."""
    from app.repositories import store
    from app.util import iso, new_id

    hub_id = new_id()
    hub = await store.insert_payment_hub({
        "id": hub_id, "org_id": "org_x", "public_token": new_id(),
        "invoice_number": "INV-0001", "amount_paise": 8500000, "currency": "INR",
        "due_date": "2026-10-01", "client_name": "Kestrel Logistics",
        "status": "active", "created_at": iso(),
    })
    assert hub["id"] == hub_id

    await store.insert_hub_contact({
        "id": new_id(), "payment_hub_id": hub_id, "role": "poc",
        "name": "Amit Rao", "phone": "+91987", "email": "a@x.com", "created_at": iso(),
    })
    await store.insert_follow_up_plan({
        "id": new_id(), "payment_hub_id": hub_id, "tone": "professional",
        "status": "approved", "approved_at": iso(), "created_at": iso(),
    })
    await store.insert_follow_up_message({
        "id": new_id(), "payment_hub_id": hub_id, "contact_role": "poc",
        "channel": "whatsapp", "category": "initial", "body": "Hi Amit...",
        "status": "scheduled", "scheduled_for": iso(), "sent_at": None,
        "created_at": iso(),
    })

    contacts = await store.list_hub_contacts(hub_id)
    assert len(contacts) == 1 and contacts[0]["role"] == "poc"

    fetched_plan = await store.get_follow_up_plan(hub_id)
    assert fetched_plan["status"] == "approved"

    msgs = await store.list_follow_up_messages_for_hub(hub_id)
    assert len(msgs) == 1 and msgs[0]["status"] == "scheduled"


@pytest.mark.asyncio
async def test_whatsapp_provider_stub_used_when_creds_missing(monkeypatch):
    """When Twilio creds are absent, `get_provider()` returns the log-only stub
    and calling `send_freeform` does not raise."""
    from app.providers import whatsapp as wa

    monkeypatch.setattr(wa.settings, "TWILIO_ACCOUNT_SID", "")
    monkeypatch.setattr(wa.settings, "TWILIO_AUTH_TOKEN", "")
    monkeypatch.setattr(wa.settings, "ORG_WHATSAPP_FROM", "")

    prov = wa.get_provider()
    assert isinstance(prov, wa.LogOnlyWhatsAppProvider)
    result = await prov.send_freeform("+15551234567", "hello")
    assert result.status == "queued"
    assert result.provider_id.startswith("stub_")
