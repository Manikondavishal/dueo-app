"""Public test webhook (Phase 0): stores the raw payload first, then verifies HMAC."""
import hashlib
import hmac
import json

from fastapi import APIRouter, HTTPException, Request

from ..config import settings
from ..repositories import store
from ..util import compare_digest, iso, new_id

router = APIRouter(prefix="/api/webhooks")

SIGNATURE_HEADER = "x-dueo-signature"


def _sign(raw: bytes) -> str:
    return hmac.new(settings.WEBHOOK_TEST_SECRET.encode(), raw, hashlib.sha256).hexdigest()


@router.post("/test")
async def webhook_test(request: Request):
    raw = await request.body()
    signature = request.headers.get(SIGNATURE_HEADER, "")
    event_id = new_id()
    # Store the payload FIRST — before verification — so nothing is lost.
    await store.insert_webhook_event(
        {
            "id": event_id,
            "raw": raw.decode("utf-8", errors="replace"),
            "signature": signature,
            "verified": False,
            "created_at": iso(),
        }
    )
    valid = compare_digest(signature, _sign(raw))
    await store.update_webhook_event(event_id, {"verified": valid})
    if not valid:
        raise HTTPException(status_code=401, detail="invalid_signature")
    try:
        payload = json.loads(raw)
    except Exception:  # noqa: BLE001
        payload = None
    return {"ok": True, "stored": True, "event_id": event_id, "payload_keys": list(payload) if isinstance(payload, dict) else None}
