"""Section 6 — authenticated business dashboard + hub detail."""
import logging

from fastapi import APIRouter, Depends, HTTPException

from ..deps import current_context
from ..repositories import store

logger = logging.getLogger("dueo.dashboard")

router = APIRouter(prefix="/api/app")


@router.get("/dashboard")
async def dashboard(ctx=Depends(current_context)):
    hubs = await store.list_payment_hubs_for_org(ctx["org_id"])
    counts = {"active": 0, "promises_due": 0, "needs_attention": 0, "paid_this_month": 0}
    for h in hubs:
        st = h.get("status")
        cr = h.get("client_response") or {}
        if st == "active":
            counts["active"] += 1
        if st == "disputed":
            counts["needs_attention"] += 1
        if cr.get("kind") == "confirmed":
            counts["promises_due"] += 1
        if st == "paid":
            counts["paid_this_month"] += 1
    # Trim to fields the table needs
    rows = [{
        "id": h["id"], "client_name": h.get("client_name"),
        "invoice_number": h.get("invoice_number"),
        "amount_paise": h.get("amount_paise"), "currency": h.get("currency"),
        "due_date": h.get("due_date"), "status": h.get("status"),
        "handling_mode": h.get("handling_mode"),
        "client_response": h.get("client_response"),
        "created_at": h.get("created_at"), "updated_at": h.get("updated_at"),
    } for h in hubs]
    return {"counts": counts, "hubs": rows, "user": ctx["user"], "org": ctx["org"]}


@router.get("/hubs/{hub_id}/conversation")
async def hub_conversation(hub_id: str, ctx=Depends(current_context)):
    """Merge follow_up_messages + whatsapp_messages into one thread, sorted
    oldest→newest. Section 6's Conversation tab reads this directly."""
    hub = await store.get_payment_hub(hub_id)
    if not hub or hub.get("org_id") != ctx["org_id"]:
        raise HTTPException(status_code=404, detail="not_found")
    fu = await store.list_follow_up_messages_for_hub(hub_id)
    wa = await store.list_whatsapp_for_hub(hub_id)
    thread = []
    business_name = ctx["org"]["display_name"]
    for m in fu:
        thread.append({
            "at": m.get("sent_at") or m.get("scheduled_for") or m.get("created_at"),
            "sender": "Dueo",
            "kind": "follow_up",
            "channel": m.get("channel"),
            "body": m.get("body"),
            "status": m.get("status"),
            "category": m.get("category"),
            # Email fallback visibility — the same body also goes out by email
            # to the snapshotted address; surfaced on the same bubble.
            "email_to": m.get("contact_email"),
            "email_status": m.get("email_status"),
        })
    for m in wa:
        if m.get("direction") == "outbound":
            # already covered by the follow_up row that produced it — skip
            # duplicates (they share the same body & timestamp)
            continue
        thread.append({
            "at": m.get("received_at") or m.get("created_at"),
            "sender": hub.get("client_name") or "Client",
            "kind": "reply",
            "channel": m.get("channel"),
            "body": m.get("body"),
            "status": m.get("status"),
        })
    # Optional self-share note when the owner chose share_myself
    if hub.get("handling_mode") == "share_myself":
        thread.append({
            "at": hub.get("updated_at") or hub.get("created_at"),
            "sender": business_name,
            "kind": "self_share",
            "channel": "manual",
            "body": "You chose to share the payment link yourself. Dueo is tracking silently.",
            "status": "info",
        })
    thread.sort(key=lambda t: t.get("at") or "")
    return {"thread": thread, "hub": hub, "business_name": business_name}
