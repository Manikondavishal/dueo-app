"""Twilio WhatsApp webhooks: inbound customer messages + outbound delivery
status callbacks. Both routes verify the `X-Twilio-Signature` header against
the exact public URL Twilio called, and both persist a single row per
`MessageSid` (idempotent under Twilio retries)."""
import logging
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from twilio.request_validator import RequestValidator

from ..config import settings
from ..repositories import store
from ..util import iso, new_id

logger = logging.getLogger("dueo.whatsapp.webhook")

router = APIRouter(prefix="/api/webhooks/twilio-whatsapp")

# Platform-managed hostnames that route to this backend. Any of them can be the
# host Twilio called; we only trust `request.url` when its hostname ends in one.
_TRUSTED_SUFFIXES = (".preview.emergentagent.com", ".emergentagent.com", ".emergentcf.cloud")


def _external_url(request: Request) -> str:
    """Twilio signs against the exact public URL IT called. The preview ingress
    forwards the *real* public host in `X-Forwarded-Host` and terminates TLS
    upstream (so `request.url.scheme` is `http`). We prefer `X-Forwarded-Host`
    when it looks like a trusted platform host, force `https`, and fall back to
    the configured APP_URL. This blocks a hostile Host header from forging a
    URL Twilio's signature would then match."""
    xfh = (request.headers.get("x-forwarded-host") or "").split(",")[0].strip().lower()
    if xfh and any(xfh.endswith(s) for s in _TRUSTED_SUFFIXES):
        return f"https://{xfh}{request.url.path}"
    host = (urlparse(str(request.url)).hostname or "").lower()
    if host and any(host.endswith(s) for s in _TRUSTED_SUFFIXES):
        return f"https://{host}{request.url.path}"
    base = (settings.APP_URL or "").rstrip("/")
    return f"{base}{request.url.path}" if base else str(request.url)


def _verify(request: Request, form: dict) -> None:
    if not settings.TWILIO_AUTH_TOKEN:
        raise HTTPException(status_code=503, detail="twilio_not_configured")
    if not settings.TWILIO_VALIDATE_SIGNATURE:
        return
    sig = request.headers.get("X-Twilio-Signature", "")
    validator = RequestValidator(settings.TWILIO_AUTH_TOKEN)
    if not validator.validate(_external_url(request), form, sig):
        raise HTTPException(status_code=403, detail="invalid_twilio_signature")


@router.post("/inbound")
async def inbound(request: Request):
    form = dict(await request.form())
    _verify(request, form)
    sid = form.get("MessageSid") or new_id()
    doc = {
        "id": sid,
        "provider_sid": sid,
        "direction": "inbound",
        "channel": "whatsapp",
        "from_addr": form.get("From"),
        "to_addr": form.get("To"),
        "body": form.get("Body", ""),
        "num_media": int(form.get("NumMedia", 0) or 0),
        "status": "received",
        "payment_hub_id": None,
        "org_id": None,
        "raw": form,
        "received_at": iso(),
        "created_at": iso(),
    }
    await store.upsert_whatsapp_message(doc)
    logger.info("wa_inbound sid=%s from=%s chars=%d", sid, form.get("From"), len(form.get("Body", "") or ""))
    # Return an empty TwiML so Twilio doesn't auto-reply on our behalf.
    return Response("<Response></Response>", media_type="application/xml")


@router.post("/status")
async def status_callback(request: Request):
    form = dict(await request.form())
    _verify(request, form)
    sid = form.get("MessageSid")
    if not sid:
        raise HTTPException(status_code=400, detail="missing_sid")
    await store.update_whatsapp_status(
        sid,
        {
            "status": form.get("MessageStatus"),
            "error_code": form.get("ErrorCode"),
            "event_type": form.get("EventType"),
            "status_updated_at": iso(),
        },
    )
    logger.info("wa_status sid=%s status=%s", sid, form.get("MessageStatus"))
    return Response(status_code=200)
