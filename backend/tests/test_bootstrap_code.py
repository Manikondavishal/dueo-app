"""Bootstrap-code route: read the latest sign-in code for ANY address while the
email sender is unverified. Guarded ONLY by CRON_SECRET (previously also
required the address to be in ADMIN_EMAILS, which blocked reading codes for
normal owner accounts)."""
import pytest
import pytest_asyncio
from fastapi import HTTPException
from motor.motor_asyncio import AsyncIOMotorClient

from app.config import settings
from app.repositories import store
from app.routers.admin import bootstrap_code
from app.util import iso, new_id

NON_ADMIN = "owner_boot@oddenough.in"


@pytest_asyncio.fixture(autouse=True)
async def _wipe():
    c = AsyncIOMotorClient(settings.MONGO_URL)
    await c[settings.DB_NAME].emails_outbox.delete_many({"to": NON_ADMIN})
    yield
    c.close()


async def _seed_code(to: str, code: str):
    await store.insert_outbox({
        "id": new_id(), "to": to, "subject": "Your Dueo sign-in code",
        "html": f"<p>Your Dueo sign-in code is <strong>{code}</strong>.</p>",
        "kind": "login_code", "provider": "resend", "status": "sent",
        "provider_id": "em_boot", "error": None, "created_at": iso(),
    })


@pytest.mark.asyncio
async def test_bootstrap_reads_code_for_non_admin_email():
    await _seed_code(NON_ADMIN, "424242")
    out = await bootstrap_code(email=NON_ADMIN, token=settings.CRON_SECRET)
    assert out["code"] == "424242"
    assert out["status"] == "sent"


@pytest.mark.asyncio
async def test_bootstrap_normalises_email_case():
    await _seed_code(NON_ADMIN, "515151")
    out = await bootstrap_code(email=NON_ADMIN.upper(), token=settings.CRON_SECRET)
    assert out["code"] == "515151"


@pytest.mark.asyncio
async def test_bootstrap_rejects_bad_token():
    await _seed_code(NON_ADMIN, "606060")
    with pytest.raises(HTTPException) as e:
        await bootstrap_code(email=NON_ADMIN, token="not-the-secret")
    assert e.value.status_code == 401
    assert e.value.detail == "invalid_token"


@pytest.mark.asyncio
async def test_bootstrap_flags_stale_code_as_unusable():
    """A code in the outbox that is no longer the live OTP must be reported
    `usable=False` rather than handed over as if it would work."""
    await _seed_code(NON_ADMIN, "717171")
    out = await bootstrap_code(email=NON_ADMIN, token=settings.CRON_SECRET)
    assert out["code"] == "717171"
    assert out["usable"] is False  # no active auth_otps row for this address


@pytest.mark.asyncio
async def test_bootstrap_404_when_no_code_for_address():
    with pytest.raises(HTTPException) as e:
        await bootstrap_code(email="nobody_boot@oddenough.in", token=settings.CRON_SECRET)
    assert e.value.status_code == 404
