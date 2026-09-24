"""Section 6 — Dashboard counts + Hub Conversation merger.

Section-6 previously had no automated pytest coverage ("session-plumbing edge
case"). We invoke the router coroutines directly with a hand-built `ctx` dict,
same pattern the section-4 approve tests use, so no HTTP/session plumbing is
needed. This covers:
  * counts bucketing (active, promises_due, needs_attention, paid_this_month)
  * conversation merger ordering (Dueo → client → self-share)
  * outbound whatsapp_messages rows are NOT duplicated in the thread
  * cross-org isolation returns 404
  * unknown hub_id returns 404
"""
import pytest
import pytest_asyncio
from fastapi import HTTPException
from motor.motor_asyncio import AsyncIOMotorClient

from app.config import settings
from app.repositories import store
from app.routers.dashboard import dashboard, hub_conversation
from app.util import gen_token, iso, new_id


@pytest_asyncio.fixture(autouse=True)
async def _wipe():
    c = AsyncIOMotorClient(settings.MONGO_URL)
    db = c[settings.DB_NAME]
    for k in ("payment_hubs", "payment_hub_contacts", "follow_up_plans",
              "follow_up_messages", "whatsapp_messages"):
        await db[k].delete_many({})
    yield
    c.close()


ORG_A = "org_dash_A"
ORG_B = "org_dash_B"


def _ctx(org_id: str = ORG_A) -> dict:
    return {
        "org_id": org_id,
        "user": {"id": "u1", "email": "owner@a.co"},
        "org": {"id": org_id, "display_name": "Alpha Co"},
    }


async def _seed_hub(org_id: str, status: str, *, client_response: dict | None = None,
                    handling_mode: str = "dueo_handles") -> str:
    hub_id = new_id()
    await store.insert_payment_hub({
        "id": hub_id, "org_id": org_id, "upload_id": "u",
        "public_token": gen_token(24),
        "invoice_number": "INV-" + hub_id[:6], "client_name": "Kestrel",
        "amount_paise": 100000, "currency": "INR", "due_date": "2026-01-01",
        "business_payment_details": "UPI: me@bank",
        "status": status, "handling_mode": handling_mode,
        "client_response": client_response,
        "llm_status": "ok", "created_at": iso(), "updated_at": iso(),
    })
    return hub_id


@pytest.mark.asyncio
async def test_dashboard_counts_bucket_correctly():
    await _seed_hub(ORG_A, "active")                              # +active
    await _seed_hub(ORG_A, "disputed")                            # +needs_attention
    await _seed_hub(ORG_A, "active",
                    client_response={"kind": "confirmed", "payment_date": "2026-02-01"})  # +active +promises_due
    await _seed_hub(ORG_A, "paid")                                # +paid_this_month
    await _seed_hub(ORG_B, "active")                              # different org, must NOT count

    out = await dashboard(ctx=_ctx(ORG_A))
    assert out["counts"] == {
        "active": 2, "promises_due": 1, "needs_attention": 1, "paid_this_month": 1,
    }
    assert len(out["hubs"]) == 4  # ORG_B's hub excluded


@pytest.mark.asyncio
async def test_hub_conversation_merges_and_orders():
    hub_id = await _seed_hub(ORG_A, "active")
    # 1) Dueo follow-up (initial), 2) client inbound reply, 3) another follow-up
    await store.insert_follow_up_message({
        "id": new_id(), "payment_hub_id": hub_id, "plan_id": "p1",
        "contact_role": "poc", "contact_name": "Amit Rao",
        "contact_phone": "+15551234567", "contact_email": "amit@k.co",
        "channel": "whatsapp", "category": "initial",
        "body": "Hi Amit, invoice due.", "status": "sent",
        "scheduled_for": "2026-01-01T09:00:00+00:00",
        "sent_at": "2026-01-01T09:00:01+00:00", "created_at": iso(),
    })
    # Outbound mirror row — must be SKIPPED in the merger to avoid a duplicate.
    await store.insert_whatsapp_message({
        "id": new_id(), "provider_sid": "SM_out_1",
        "direction": "outbound", "channel": "whatsapp",
        "from_addr": None, "to_addr": "+15551234567", "to_name": "Amit Rao",
        "body": "Hi Amit, invoice due.", "num_media": 0, "status": "sent",
        "payment_hub_id": hub_id, "org_id": ORG_A,
        "created_at": "2026-01-01T09:00:01+00:00",
    })
    # Inbound client reply
    await store.insert_whatsapp_message({
        "id": new_id(), "provider_sid": "SM_in_1",
        "direction": "inbound", "channel": "whatsapp",
        "from_addr": "+15551234567", "to_addr": None,
        "body": "will pay next week", "num_media": 0, "status": "received",
        "payment_hub_id": hub_id, "org_id": ORG_A,
        "received_at": "2026-01-01T10:00:00+00:00",
        "created_at": "2026-01-01T10:00:00+00:00",
    })

    out = await hub_conversation(hub_id, ctx=_ctx(ORG_A))
    assert out["hub"]["id"] == hub_id
    thread = out["thread"]

    # No duplicate of the outbound WA row — only the follow_up + inbound remain.
    assert len(thread) == 2, [t["body"] for t in thread]
    assert thread[0]["sender"] == "Alpha Co" or thread[0]["sender"] == "Dueo"
    assert thread[0]["kind"] == "follow_up"
    assert thread[0]["body"] == "Hi Amit, invoice due."
    assert thread[1]["kind"] == "reply"
    assert thread[1]["sender"] == "Kestrel"
    assert thread[1]["body"] == "will pay next week"
    # Sort order (oldest → newest)
    assert thread[0]["at"] < thread[1]["at"]


@pytest.mark.asyncio
async def test_hub_conversation_self_share_appends_info_row():
    hub_id = await _seed_hub(ORG_A, "active", handling_mode="share_myself")
    out = await hub_conversation(hub_id, ctx=_ctx(ORG_A))
    kinds = [t["kind"] for t in out["thread"]]
    assert "self_share" in kinds


@pytest.mark.asyncio
async def test_hub_conversation_cross_org_404():
    hub_id = await _seed_hub(ORG_B, "active")
    with pytest.raises(HTTPException) as e:
        await hub_conversation(hub_id, ctx=_ctx(ORG_A))
    assert e.value.status_code == 404


@pytest.mark.asyncio
async def test_hub_conversation_unknown_id_404():
    with pytest.raises(HTTPException) as e:
        await hub_conversation("no_such_hub", ctx=_ctx(ORG_A))
    assert e.value.status_code == 404


@pytest.mark.asyncio
async def test_dashboard_isolation_empty_for_new_org():
    await _seed_hub(ORG_A, "active")
    out = await dashboard(ctx=_ctx(ORG_B))
    assert out["counts"] == {"active": 0, "promises_due": 0, "needs_attention": 0, "paid_this_month": 0}
    assert out["hubs"] == []



@pytest.mark.asyncio
async def test_hub_conversation_exposes_email_fallback_state():
    """Every Dueo bubble carries the snapshotted email address + the fallback
    email's outcome so the Conversation tab can annotate one bubble per send
    (no duplicate email rows). Client replies never carry email fields."""
    hub_id = await _seed_hub(ORG_A, "active")
    await store.insert_follow_up_message({
        "id": new_id(), "payment_hub_id": hub_id, "plan_id": "p1",
        "contact_role": "poc", "contact_name": "Amit Rao",
        "contact_phone": "+15551234567", "contact_email": "amit@k.co",
        "channel": "whatsapp", "category": "initial",
        "body": "Hi Amit, invoice due.", "status": "sent",
        "email_status": "sent", "email_provider_id": "em_1",
        "scheduled_for": "2026-01-01T09:00:00+00:00",
        "sent_at": "2026-01-01T09:00:01+00:00", "created_at": iso(),
    })
    await store.insert_follow_up_message({
        "id": new_id(), "payment_hub_id": hub_id, "plan_id": "p1",
        "contact_role": "poc", "contact_name": "Amit Rao",
        "contact_phone": "+15551234567", "contact_email": "amit@k.co",
        "channel": "whatsapp", "category": "follow_up",
        "body": "Gentle nudge.", "status": "sent",
        "email_status": "failed",
        "scheduled_for": "2026-01-04T09:00:00+00:00",
        "sent_at": "2026-01-04T09:00:01+00:00", "created_at": iso(),
    })
    await store.insert_whatsapp_message({
        "id": new_id(), "provider_sid": "SM_in_2",
        "direction": "inbound", "channel": "whatsapp",
        "from_addr": "+15551234567", "to_addr": None,
        "body": "ok", "num_media": 0, "status": "received",
        "payment_hub_id": hub_id, "org_id": ORG_A,
        "received_at": "2026-01-05T10:00:00+00:00",
        "created_at": "2026-01-05T10:00:00+00:00",
    })

    thread = (await hub_conversation(hub_id, ctx=_ctx(ORG_A)))["thread"]
    dueo = [t for t in thread if t["kind"] == "follow_up"]
    assert len(dueo) == 2  # still one bubble per send, no separate email rows
    assert dueo[0]["email_to"] == "amit@k.co"
    assert dueo[0]["email_status"] == "sent"
    assert dueo[1]["email_status"] == "failed"
    reply = next(t for t in thread if t["kind"] == "reply")
    assert reply.get("email_to") is None
