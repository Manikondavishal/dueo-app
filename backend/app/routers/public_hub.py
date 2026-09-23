"""Section 5 — public payment hub. Unauthenticated by design; the only thing
identifying a hub is the `public_token` (opaque, 24-char, unique). Rate-limits
are inherited from the shared middleware. No client-supplied `Origin` bypass
because state-changing routes still go through the same-origin check."""
import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from ..repositories import store
from ..util import iso, new_id

logger = logging.getLogger("dueo.public_hub")

router = APIRouter(prefix="/api/public/hub")


class ConfirmIn(BaseModel):
    payment_date: str = Field(min_length=8, max_length=32)  # YYYY-MM-DD


class IssueIn(BaseModel):
    note: str = Field(min_length=1, max_length=1000)


def _valid_date(s: str) -> bool:
    try:
        datetime.strptime(s, "%Y-%m-%d")
        return True
    except ValueError:
        return False


async def _timeline(hub: dict) -> list[dict]:
    hub_id = hub["id"]
    events: list[dict] = [{
        "kind": "payment_due",
        "at": hub.get("due_date") or hub.get("created_at"),
        "label": "Payment due",
        "detail": hub.get("due_date") or "",
    }]
    for m in await store.list_follow_up_messages_for_hub(hub_id):
        if m.get("status") == "sent":
            events.append({
                "kind": "follow_up_sent",
                "at": m.get("sent_at") or m.get("scheduled_for"),
                "label": f"Follow-up sent ({m.get('category', 'initial').replace('_', '-')})",
                "detail": (m.get("body") or "").split("\n")[0][:120],
            })
    if hub.get("viewed_at"):
        events.append({
            "kind": "viewed",
            "at": hub["viewed_at"],
            "label": "Client opened this page",
            "detail": "",
        })
    for m in await store.list_whatsapp_for_hub(hub_id):
        if m.get("direction") == "inbound":
            events.append({
                "kind": "client_reply",
                "at": m.get("received_at") or m.get("created_at"),
                "label": "Client replied on WhatsApp",
                "detail": (m.get("body") or "")[:200],
            })
    cr = hub.get("client_response")
    if cr:
        events.append({
            "kind": cr.get("kind", "responded"),
            "at": cr.get("submitted_at"),
            "label": "Confirmed payment date" if cr.get("kind") == "confirmed" else "Client flagged an issue",
            "detail": cr.get("payment_date") if cr.get("kind") == "confirmed" else (cr.get("note") or "")[:200],
        })
    events.sort(key=lambda e: e.get("at") or "")
    return events


def _redact(hub: dict) -> dict:
    """Only expose fields safe for the public. Never leak org_id, upload_id,
    org internals, or ML provenance."""
    return {
        "invoice_number": hub.get("invoice_number"),
        "client_name": hub.get("client_name"),
        "amount_paise": hub.get("amount_paise"),
        "currency": hub.get("currency"),
        "due_date": hub.get("due_date"),
        "business_name": hub.get("business_name"),
        "business_payment_details": hub.get("business_payment_details"),
        "status": hub.get("status"),
        "public_token": hub.get("public_token"),
        "created_at": hub.get("created_at"),
        "viewed_at": hub.get("viewed_at"),
    }


@router.get("/{token}")
async def read_public_hub(token: str, request: Request):
    hub = await store.get_payment_hub_by_token(token)
    if not hub:
        raise HTTPException(status_code=404, detail="not_found")
    if not hub.get("viewed_at"):
        await store.update_payment_hub(hub["id"], {"viewed_at": iso()})
        hub["viewed_at"] = iso()
    # Attach the business display name for the header — safe, already public.
    org = await store.get_org(hub["org_id"])
    hub["business_name"] = (org or {}).get("display_name") or ""
    timeline = await _timeline(hub)
    return {"hub": _redact(hub), "timeline": timeline}


@router.post("/{token}/confirm")
async def confirm_payment(token: str, body: ConfirmIn):
    if not _valid_date(body.payment_date):
        raise HTTPException(status_code=400, detail="bad_date")
    hub = await store.get_payment_hub_by_token(token)
    if not hub:
        raise HTTPException(status_code=404, detail="not_found")
    await store.update_payment_hub(hub["id"], {
        "client_response": {
            "kind": "confirmed",
            "payment_date": body.payment_date,
            "submitted_at": iso(),
        },
        "updated_at": iso(),
    })
    return {"ok": True}


@router.post("/{token}/issue")
async def flag_issue(token: str, body: IssueIn):
    hub = await store.get_payment_hub_by_token(token)
    if not hub:
        raise HTTPException(status_code=404, detail="not_found")
    await store.update_payment_hub(hub["id"], {
        "status": "disputed",  # pauses any scheduler tick that filters by status
        "client_response": {
            "kind": "issue",
            "note": body.note.strip(),
            "submitted_at": iso(),
        },
        "updated_at": iso(),
    })
    logger.info("client flagged issue hub=%s len=%d", hub["id"], len(body.note))
    return {"ok": True}
