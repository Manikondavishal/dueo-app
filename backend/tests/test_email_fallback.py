"""Email fallback for the follow-up pipe. Every WhatsApp send fires an
independent email to the same contact's snapshotted address; email failures
must NEVER fail the WA send. These tests use a monkeypatch on
`email_provider.send_email` so nothing actually hits the Emergent mail proxy."""
from unittest.mock import patch, AsyncMock

import pytest
import pytest_asyncio
from motor.motor_asyncio import AsyncIOMotorClient

from app.config import settings
from app.providers.whatsapp import SentMessage
from app.repositories import store
from app.services import follow_ups
from app.util import gen_token, iso, new_id


ORG = "org_email_fb"


@pytest_asyncio.fixture(autouse=True)
async def _wipe():
    c = AsyncIOMotorClient(settings.MONGO_URL)
    db = c[settings.DB_NAME]
    for k in ("payment_hubs", "payment_hub_contacts", "follow_up_plans",
              "follow_up_messages", "whatsapp_messages", "emails_outbox",
              "organizations"):
        await db[k].delete_many({})
    yield
    c.close()


async def _seed_org_hub_with_schedule():
    await store.insert_org({"id": ORG, "display_name": "Alpha Co", "created_at": iso()})
    hub_id = new_id()
    await store.insert_payment_hub({
        "id": hub_id, "org_id": ORG, "upload_id": "u",
        "public_token": gen_token(16), "invoice_number": "INV-EM",
        "client_name": "Kestrel", "amount_paise": 100000,
        "currency": "INR", "due_date": "2026-01-01",
        "business_payment_details": "",
        "status": "active", "handling_mode": "dueo_handles",
        "llm_status": "ok", "created_at": iso(), "updated_at": iso(),
    })
    poc = {"name": "Amit Rao", "phone": "+15551234567", "email": "amit@kestrel.co"}
    rows = follow_ups.build_scheduled_rows(
        hub={"id": hub_id, "due_date": "2026-01-01",
             "invoice_number": "INV-EM", "client_name": "Kestrel",
             "amount_paise": 100000, "public_token": "t"},
        plan_id="p1", tone="professional", poc=poc, esc1=None,
        business_name="Alpha Co", public_base="https://a.co",
    )
    await store.insert_follow_up_messages_bulk(rows)
    return hub_id


@pytest.mark.asyncio
async def test_dispatch_also_sends_email_to_snapshot_address():
    hub_id = await _seed_org_hub_with_schedule()
    cutoff = "2027-01-01T00:00:00+00:00"

    class Fake:
        i = 0
        async def send_freeform(self, to, body, status_callback=None):
            Fake.i += 1
            return SentMessage(provider_id=f"SM_ok_{Fake.i}", status="queued")

    fake_email = AsyncMock(return_value={"status": "sent", "provider_id": "eid_1"})

    with patch("app.services.follow_ups.wa_provider", Fake()), \
         patch("app.services.follow_ups.email_provider.send_email", fake_email):
        summary = await follow_ups.dispatch_due(now_iso=cutoff)

    assert summary["sent"] == 4
    # 4 emails fired, each to the snapshotted contact_email
    assert fake_email.await_count == 4
    for call in fake_email.await_args_list:
        assert call.kwargs["to"] == "amit@kestrel.co"
        assert call.kwargs["kind"] == "follow_up"
        assert "INV-EM" in call.kwargs["subject"]
        assert "Kestrel" in call.kwargs["html"] or "Amit" in call.kwargs["html"]
    # Each follow_up_messages row records the email outcome
    fu = await store.list_follow_up_messages_for_hub(hub_id)
    assert all(r["email_status"] == "sent" for r in fu)
    assert all(r["email_provider_id"] == "eid_1" for r in fu)


@pytest.mark.asyncio
async def test_email_failure_does_not_fail_whatsapp_send():
    hub_id = await _seed_org_hub_with_schedule()
    cutoff = "2027-01-01T00:00:00+00:00"

    class Fake:
        i = 0
        async def send_freeform(self, to, body, status_callback=None):
            Fake.i += 1
            return SentMessage(provider_id=f"SM_boom_{Fake.i}", status="queued")

    boom_email = AsyncMock(side_effect=RuntimeError("email 401 invalid"))

    with patch("app.services.follow_ups.wa_provider", Fake()), \
         patch("app.services.follow_ups.email_provider.send_email", boom_email):
        summary = await follow_ups.dispatch_due(now_iso=cutoff)

    # WA succeeded on every row despite the email exception
    assert summary == {"sent": 4, "failed": 0, "skipped": 0, "cutoff": cutoff}
    fu = await store.list_follow_up_messages_for_hub(hub_id)
    assert all(r["status"] == "sent" for r in fu)
    assert all(r.get("email_status") is None for r in fu)


@pytest.mark.asyncio
async def test_email_skipped_when_no_contact_email():
    """A scheduled row with no email address should NOT touch the email pipe."""
    await store.insert_org({"id": ORG, "display_name": "Alpha Co", "created_at": iso()})
    hub_id = new_id()
    await store.insert_payment_hub({
        "id": hub_id, "org_id": ORG, "upload_id": "u",
        "public_token": gen_token(16), "invoice_number": "INV-NE",
        "client_name": "Kestrel", "amount_paise": 100000, "currency": "INR",
        "due_date": "2026-01-01", "business_payment_details": "",
        "status": "active", "llm_status": "ok",
        "created_at": iso(), "updated_at": iso(),
    })
    row_id = new_id()
    await store.insert_follow_up_message({
        "id": row_id, "payment_hub_id": hub_id, "plan_id": "p",
        "contact_role": "poc", "contact_name": "Amit",
        "contact_phone": "+15551234567", "contact_email": None,
        "channel": "whatsapp", "category": "follow_up",
        "body": "…", "status": "scheduled",
        "scheduled_for": "2026-01-05T09:00:00+00:00", "created_at": iso(),
    })
    class Fake:
        async def send_freeform(self, to, body, status_callback=None):
            return SentMessage(provider_id="SM_3", status="queued")
    fake_email = AsyncMock()
    with patch("app.services.follow_ups.wa_provider", Fake()), \
         patch("app.services.follow_ups.email_provider.send_email", fake_email):
        await follow_ups.dispatch_due(now_iso="2027-01-01T00:00:00+00:00")
    assert fake_email.await_count == 0
