"""Tests for Section 4 — templates + approve flow.

The approve flow calls the WhatsApp provider. We monkeypatch it with a fake
that records the send so tests never hit Twilio."""
from unittest.mock import patch

import pytest
import pytest_asyncio
from motor.motor_asyncio import AsyncIOMotorClient

from app.config import settings
from app.providers.whatsapp import SentMessage
from app.repositories import store
from app.services import templates as tmpl
from app.util import gen_token, iso, new_id


@pytest_asyncio.fixture(autouse=True)
async def _wipe():
    c = AsyncIOMotorClient(settings.MONGO_URL)
    db = c[settings.DB_NAME]
    for k in ("payment_hubs", "payment_hub_contacts", "follow_up_plans",
              "follow_up_messages", "whatsapp_messages"):
        await db[k].delete_many({})
    yield
    c.close()


async def _seed_ready() -> tuple[str, str]:
    hub_id = new_id()
    org_id = "org_s4"
    await store.insert_payment_hub({
        "id": hub_id, "org_id": org_id, "upload_id": "u1",
        "public_token": gen_token(24), "invoice_number": "INV-0417",
        "client_name": "Kestrel Logistics", "amount_paise": 8500000,
        "currency": "INR", "due_date": "2026-09-07",
        "business_payment_details": "UPI: me@bank",
        "status": "draft", "llm_status": "ok", "created_at": iso(),
    })
    await store.replace_hub_contacts(hub_id, [{
        "id": new_id(), "payment_hub_id": hub_id, "role": "poc",
        "name": "Amit Rao", "phone": "+15551234567",
        "email": "amit@kestrel.co", "created_at": iso(),
    }])
    return hub_id, org_id


def test_templates_render_all_9_combinations():
    hub = {"invoice_number": "INV-01", "amount_paise": 100000,
           "due_date": "2026-01-01", "public_token": "tok",
           "client_name": "Kestrel"}
    poc = {"name": "Amit Rao"}
    esc = {"name": "Priya Nair"}
    for tone in tmpl.TONES:
        for cat in tmpl.CATEGORIES:
            out = tmpl.render(tone, cat, hub, poc, esc, "Upload Co", "https://x")
            assert "INV-01" in out
            assert "1,000" in out  # ₹1,000
            assert "https://x/hub/tok" in out
            if cat == "escalation":
                assert "Priya" in out


def test_templates_soft_fallbacks_when_data_missing():
    hub = {"invoice_number": None, "amount_paise": None, "due_date": None,
           "public_token": "t"}
    out = tmpl.render("professional", "initial", hub, None, None, "", "")
    assert "—" in out          # invoice_number fallback
    assert "₹0" in out         # amount fallback
    assert "the due date" in out


@pytest.mark.asyncio
async def test_approve_creates_plan_message_and_marks_hub_active():
    hub_id, org_id = await _seed_ready()

    fake_provider_sid = "SM_fake_" + new_id()[:6]

    class FakeProvider:
        sent: list[tuple] = []
        async def send_freeform(self, to, body, status_callback=None):
            self.sent.append((to, body))
            return SentMessage(provider_id=fake_provider_sid, status="queued")

    fake = FakeProvider()
    with patch("app.routers.hubs.wa_provider", fake):
        from app.routers.hubs import approve_plan, ApproveIn
        ctx = {"org_id": org_id, "org": {"display_name": "Upload Co"},
               "user": {"id": "u1"}}
        result = await approve_plan(hub_id, ApproveIn(tone="warm", consent=True), ctx=ctx)

    assert result["plan"]["status"] == "approved"
    assert result["plan"]["tone"] == "warm"
    assert result["message"]["status"] == "sent"
    assert result["message"]["provider_sid"] == fake_provider_sid
    assert result["send_error"] is None
    assert fake.sent and fake.sent[0][0] == "+15551234567"

    hub = await store.get_payment_hub(hub_id)
    assert hub["status"] == "active"

    wa = await store.list_whatsapp_for_hub(hub_id)
    assert len(wa) == 1 and wa[0]["direction"] == "outbound"


@pytest.mark.asyncio
async def test_approve_requires_consent_and_primary():
    hub_id, org_id = await _seed_ready()
    from app.routers.hubs import approve_plan, ApproveIn
    from fastapi import HTTPException

    ctx = {"org_id": org_id, "org": {"display_name": "Upload Co"}, "user": {"id": "u1"}}
    with pytest.raises(HTTPException) as e:
        await approve_plan(hub_id, ApproveIn(tone="professional", consent=False), ctx=ctx)
    assert e.value.status_code == 400 and e.value.detail == "consent_required"

    # remove primary and ensure it blocks
    await store.replace_hub_contacts(hub_id, [])
    with pytest.raises(HTTPException) as e2:
        await approve_plan(hub_id, ApproveIn(tone="professional", consent=True), ctx=ctx)
    assert e2.value.status_code == 400 and e2.value.detail == "no_primary_contact"


@pytest.mark.asyncio
async def test_approve_records_send_failure_but_still_creates_plan():
    hub_id, org_id = await _seed_ready()

    class BoomProvider:
        async def send_freeform(self, to, body, status_callback=None):
            raise RuntimeError("simulated twilio outage")

    with patch("app.routers.hubs.wa_provider", BoomProvider()):
        from app.routers.hubs import approve_plan, ApproveIn
        ctx = {"org_id": org_id, "org": {"display_name": "Upload Co"}, "user": {"id": "u1"}}
        result = await approve_plan(hub_id, ApproveIn(tone="firm", consent=True), ctx=ctx)

    assert result["send_error"] and "simulated twilio outage" in result["send_error"]
    assert result["message"]["status"] == "failed"
    hub = await store.get_payment_hub(hub_id)
    assert hub["status"] == "active"  # plan still exists, retry-able later
