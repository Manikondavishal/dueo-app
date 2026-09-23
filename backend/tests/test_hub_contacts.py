"""Tests for Section 3 — payment hub contacts (replace-semantics)."""
import pytest
import pytest_asyncio
from motor.motor_asyncio import AsyncIOMotorClient

from app.config import settings
from app.repositories import store
from app.util import gen_token, iso, new_id


@pytest_asyncio.fixture(autouse=True)
async def _wipe():
    client = AsyncIOMotorClient(settings.MONGO_URL)
    db = client[settings.DB_NAME]
    await db.payment_hubs.delete_many({})
    await db.payment_hub_contacts.delete_many({})
    yield
    client.close()


async def _seed() -> str:
    hub_id = new_id()
    await store.insert_payment_hub({
        "id": hub_id, "org_id": "org_c", "upload_id": "u1",
        "public_token": gen_token(24), "invoice_number": "INV-C",
        "client_name": "C", "amount_paise": 100000, "currency": "INR",
        "due_date": "2026-11-01", "business_payment_details": "UPI: a@b",
        "status": "draft", "llm_status": "ok", "created_at": iso(),
    })
    return hub_id


@pytest.mark.asyncio
async def test_replace_contacts_wipes_and_reinserts():
    hub_id = await _seed()
    rows_a = [{
        "id": new_id(), "payment_hub_id": hub_id, "role": "poc",
        "name": "Amit Rao", "phone": "+91 98765 43210", "email": "amit@x.com",
        "created_at": iso(),
    }]
    saved_a = await store.replace_hub_contacts(hub_id, rows_a)
    assert len(saved_a) == 1 and saved_a[0]["role"] == "poc"

    rows_b = [
        {"id": new_id(), "payment_hub_id": hub_id, "role": "poc",
         "name": "Kavya", "phone": "+91 90000 00001", "email": "k@x.com", "created_at": iso()},
        {"id": new_id(), "payment_hub_id": hub_id, "role": "escalation_1",
         "name": "Priya", "phone": "+91 90000 00002", "email": "p@x.com", "created_at": iso()},
    ]
    saved_b = await store.replace_hub_contacts(hub_id, rows_b)
    assert [c["role"] for c in saved_b] == ["poc", "escalation_1"]
    listed = await store.list_hub_contacts(hub_id)
    assert len(listed) == 2
    assert all(c["name"] != "Amit Rao" for c in listed)


@pytest.mark.asyncio
async def test_replace_contacts_empty_wipes():
    hub_id = await _seed()
    await store.replace_hub_contacts(hub_id, [{
        "id": new_id(), "payment_hub_id": hub_id, "role": "poc",
        "name": "N", "phone": "+91 98765 43210", "email": "n@x.com", "created_at": iso(),
    }])
    await store.replace_hub_contacts(hub_id, [])
    assert await store.list_hub_contacts(hub_id) == []
