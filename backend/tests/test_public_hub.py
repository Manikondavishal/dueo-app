"""Tests for Section 5 — public payment hub."""
import httpx
import pytest
import pytest_asyncio
from motor.motor_asyncio import AsyncIOMotorClient

from app.config import settings
from app.repositories import store
from app.util import gen_token, iso, new_id

API = settings.APP_URL.rstrip("/") + "/api"


@pytest_asyncio.fixture(autouse=True)
async def _wipe():
    c = AsyncIOMotorClient(settings.MONGO_URL)
    db = c[settings.DB_NAME]
    for k in ("payment_hubs", "orgs", "follow_up_messages", "whatsapp_messages"):
        await db[k].delete_many({"_id": {"$regex": "^testpub"}})
    yield
    c.close()


async def _seed_hub() -> str:
    org_id = "testpub_org_" + new_id()[:6]
    hub_id = "testpub_hub_" + new_id()[:6]
    token = "testpubtok_" + gen_token(16)
    await store.insert_org({"id": org_id, "display_name": "Meridian Studio",
                            "country": "IN", "created_at": iso()})
    await store.insert_payment_hub({
        "id": hub_id, "org_id": org_id, "upload_id": "u1",
        "public_token": token, "invoice_number": "INV-0417",
        "client_name": "Kestrel Logistics", "amount_paise": 8500000,
        "currency": "INR", "due_date": "2026-09-07",
        "business_payment_details": "UPI: meridian@hdfcbank",
        "status": "active", "llm_status": "ok", "created_at": iso(),
    })
    return token


@pytest.mark.asyncio
async def test_public_get_returns_redacted_hub_and_sets_viewed_at():
    token = await _seed_hub()
    async with httpx.AsyncClient(base_url=API, timeout=20) as h:
        r = await h.get(f"/public/hub/{token}")
    assert r.status_code == 200
    body = r.json()
    hub = body["hub"]
    assert hub["invoice_number"] == "INV-0417"
    assert hub["amount_paise"] == 8500000
    assert hub["business_name"] == "Meridian Studio"
    # redacted fields must NOT leak
    assert "org_id" not in hub
    assert "upload_id" not in hub
    assert "llm_status" not in hub
    assert hub["viewed_at"] is not None
    assert body["timeline"]  # payment_due entry at minimum


@pytest.mark.asyncio
async def test_public_confirm_records_payment_date_and_appears_in_timeline():
    token = await _seed_hub()
    async with httpx.AsyncClient(base_url=API, timeout=20) as h:
        r = await h.post(f"/public/hub/{token}/confirm",
                         json={"payment_date": "2026-10-01"},
                         headers={"Origin": settings.APP_URL})
        assert r.status_code == 200
        r2 = await h.get(f"/public/hub/{token}")
        kinds = [e["kind"] for e in r2.json()["timeline"]]
        assert "confirmed" in kinds


@pytest.mark.asyncio
async def test_public_issue_flips_hub_to_disputed():
    token = await _seed_hub()
    async with httpx.AsyncClient(base_url=API, timeout=20) as h:
        r = await h.post(f"/public/hub/{token}/issue",
                         json={"note": "Wrong amount — we agreed on 80k not 85k."},
                         headers={"Origin": settings.APP_URL})
        assert r.status_code == 200
        r2 = await h.get(f"/public/hub/{token}")
    hub = r2.json()["hub"]
    assert hub["status"] == "disputed"
    assert any(e["kind"] == "issue" for e in r2.json()["timeline"])


@pytest.mark.asyncio
async def test_public_bad_token_404():
    async with httpx.AsyncClient(base_url=API, timeout=20) as h:
        r = await h.get("/public/hub/does-not-exist")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_public_bad_date_400():
    token = await _seed_hub()
    async with httpx.AsyncClient(base_url=API, timeout=20) as h:
        r = await h.post(f"/public/hub/{token}/confirm",
                         json={"payment_date": "not-a-date"},
                         headers={"Origin": settings.APP_URL})
    assert r.status_code == 400
