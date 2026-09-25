"""Own-key Resend transport: request shape, id capture, and error handling.

No network — `httpx.AsyncClient.post` is patched. These tests pin the contract
the live Resend API expects (Bearer auth, User-Agent, `from`/`to`/`subject`
/`html`) so a future refactor can't silently regress it back to the retired
Emergent-managed pipe.
"""
import httpx
import pytest

from app.config import settings
from app.providers import email as email_provider


class _Rec:
    def __init__(self):
        self.url = None
        self.headers = None
        self.json = None


@pytest.fixture
def captured(monkeypatch):
    rec = _Rec()

    def _factory(status_code: int, body: dict | str):
        async def _post(self, url, headers=None, json=None, **kw):
            rec.url, rec.headers, rec.json = url, headers, json
            if isinstance(body, dict):
                return httpx.Response(status_code, json=body)
            return httpx.Response(status_code, text=body)
        monkeypatch.setattr(httpx.AsyncClient, "post", _post)
        return rec

    return _factory


@pytest.mark.asyncio
async def test_resend_request_shape_and_id(captured, monkeypatch):
    monkeypatch.setattr(settings, "EMAIL_PROVIDER", "resend")
    monkeypatch.setattr(settings, "RESEND_API_KEY", "re_test_key")
    monkeypatch.setattr(settings, "RESEND_FROM", "onboarding@resend.dev")
    rec = captured(200, {"id": "msg_abc123"})

    out = await email_provider.send_email(
        to="vishalmanikonda@icloud.com", subject="Your Dueo code",
        html="<p>123456</p>", kind="login_code",
    )

    assert out == {"status": "sent", "provider_id": "msg_abc123"}
    assert rec.url == "https://api.resend.com/emails"
    assert rec.headers["Authorization"] == "Bearer re_test_key"
    assert rec.headers["User-Agent"]  # Resend 403s without one
    assert rec.json["from"] == "Dueo <onboarding@resend.dev>"
    assert rec.json["to"] == ["vishalmanikonda@icloud.com"]
    assert rec.json["subject"] == "Your Dueo code"
    assert rec.json["html"] == "<p>123456</p>"


@pytest.mark.asyncio
async def test_resend_403_recorded_as_failed_with_body(captured, monkeypatch):
    """The resend.dev sender can only mail the account owner; Resend answers
    403. The send must not raise — it lands in the outbox as `failed` with the
    provider body preserved."""
    monkeypatch.setattr(settings, "EMAIL_PROVIDER", "resend")
    monkeypatch.setattr(settings, "RESEND_API_KEY", "re_test_key")
    captured(403, {"name": "validation_error",
                   "message": "You can only send testing emails to your own email address"})

    out = await email_provider.send_email(
        to="amit@kestrel.co.in", subject="Reminder: invoice INV-0417",
        html="<p>due</p>", kind="follow_up",
    )
    assert out["status"] == "failed"
    assert out["provider_id"] is None

    row = (await email_provider.store.list_outbox(1))[0]
    assert row["status"] == "failed"
    assert "403" in row["error"] and "validation_error" in row["error"]


@pytest.mark.asyncio
async def test_no_key_falls_back_to_outbox_only(monkeypatch):
    monkeypatch.setattr(settings, "EMAIL_PROVIDER", "resend")
    monkeypatch.setattr(settings, "RESEND_API_KEY", "")

    async def _boom(*a, **kw):  # must never be called
        raise AssertionError("network call attempted without a key")
    monkeypatch.setattr(httpx.AsyncClient, "post", _boom)

    out = await email_provider.send_email(
        to="vishalmanikonda@icloud.com", subject="s", html="<p>x</p>", kind="invite",
    )
    assert out == {"status": "outbox", "provider_id": None}


@pytest.mark.asyncio
async def test_emergent_email_pipe_is_gone():
    src = open(email_provider.__file__).read()
    assert "integrations.emergentagent.com" not in src
    assert "X-Email-Key" not in src
    assert "settings.EMERGENT_EMAIL_KEY" not in src  # only a docstring mention remains
