"""Mark-as-paid tests. Verifies the endpoint flips status, cancels every
still-scheduled follow-up, is idempotent, and enforces tenant isolation."""
import pytest
import pytest_asyncio
from fastapi import HTTPException
from motor.motor_asyncio import AsyncIOMotorClient

from app.config import settings
from app.repositories import store
from app.routers.hubs import mark_paid
from app.util import gen_token, iso, new_id


ORG = "org_mp"


@pytest_asyncio.fixture(autouse=True)
async def _wipe():
    c = AsyncIOMotorClient(settings.MONGO_URL)
    db = c[settings.DB_NAME]
    for k in ("payment_hubs", "follow_up_messages"):
        await db[k].delete_many({})
    yield
    c.close()


def _ctx(org_id: str = ORG) -> dict:
    return {"org_id": org_id, "user": {"id": "owner1"}, "org": {"id": org_id, "display_name": "A"}}


async def _seed_hub(org_id: str = ORG, status: str = "active") -> str:
    hub_id = new_id()
    await store.insert_payment_hub({
        "id": hub_id, "org_id": org_id, "upload_id": "u",
        "public_token": gen_token(16), "invoice_number": "INV",
        "client_name": "K", "amount_paise": 100000, "currency": "INR",
        "due_date": "2026-01-01", "business_payment_details": "",
        "status": status, "handling_mode": "dueo_handles",
        "llm_status": "ok", "created_at": iso(), "updated_at": iso(),
    })
    return hub_id


async def _seed_two_scheduled(hub_id: str) -> None:
    for i in range(2):
        await store.insert_follow_up_message({
            "id": new_id(), "payment_hub_id": hub_id, "plan_id": "p",
            "contact_role": "poc", "contact_name": "N", "contact_phone": "+11",
            "contact_email": "a@a.co", "channel": "whatsapp", "category": "follow_up",
            "body": "…", "status": "scheduled",
            "scheduled_for": f"2026-01-1{i}T09:00:00+00:00",
            "sent_at": None, "created_at": iso(),
        })


@pytest.mark.asyncio
async def test_mark_paid_flips_status_and_cancels_all_scheduled():
    hub_id = await _seed_hub()
    await _seed_two_scheduled(hub_id)

    result = await mark_paid(hub_id, ctx=_ctx())

    assert result["already_paid"] is False
    assert result["canceled"] == 2
    assert result["hub"]["status"] == "paid"
    assert result["hub"]["paid_at"]
    assert result["hub"]["paid_by"] == "owner1"
    fu = await store.list_follow_up_messages_for_hub(hub_id)
    assert [m["status"] for m in fu] == ["canceled", "canceled"]
    assert all(m["canceled_reason"] == "marked_paid" for m in fu)


@pytest.mark.asyncio
async def test_mark_paid_is_idempotent():
    hub_id = await _seed_hub()
    await mark_paid(hub_id, ctx=_ctx())
    # Second call: no scheduled rows to cancel, status unchanged, already_paid=True
    r2 = await mark_paid(hub_id, ctx=_ctx())
    assert r2["already_paid"] is True
    assert r2["canceled"] == 0
    assert r2["hub"]["status"] == "paid"


@pytest.mark.asyncio
async def test_mark_paid_does_not_touch_already_sent_rows():
    hub_id = await _seed_hub()
    # One scheduled + one already sent
    await store.insert_follow_up_message({
        "id": new_id(), "payment_hub_id": hub_id, "plan_id": "p",
        "contact_role": "poc", "contact_name": "N", "contact_phone": "+11",
        "contact_email": "a@a.co", "channel": "whatsapp", "category": "follow_up",
        "body": "…", "status": "scheduled",
        "scheduled_for": "2026-01-05T09:00:00+00:00", "created_at": iso(),
    })
    sent_id = new_id()
    await store.insert_follow_up_message({
        "id": sent_id, "payment_hub_id": hub_id, "plan_id": "p",
        "contact_role": "poc", "contact_name": "N", "contact_phone": "+11",
        "contact_email": "a@a.co", "channel": "whatsapp", "category": "initial",
        "body": "…", "status": "sent",
        "scheduled_for": "2026-01-01T09:00:00+00:00",
        "sent_at": "2026-01-01T09:00:01+00:00", "created_at": iso(),
    })
    r = await mark_paid(hub_id, ctx=_ctx())
    assert r["canceled"] == 1
    fu = await store.list_follow_up_messages_for_hub(hub_id)
    sent = [m for m in fu if m["id"] == sent_id][0]
    assert sent["status"] == "sent"  # untouched


@pytest.mark.asyncio
async def test_mark_paid_cross_org_404():
    hub_id = await _seed_hub()
    with pytest.raises(HTTPException) as e:
        await mark_paid(hub_id, ctx=_ctx(org_id="other_org"))
    assert e.value.status_code == 404
