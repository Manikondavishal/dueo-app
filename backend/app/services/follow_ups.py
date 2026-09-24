"""Follow-up scheduling + dispatch (Section 8, Scheduler Tick).

Two responsibilities, kept in one file so the "snapshot at approve time"
invariant is enforced from a single place:

1. `build_scheduled_rows(...)` — called at approve time. Given the hub, the
   loaded contacts (poc + optional escalation_1), and the tone, returns the 4
   `follow_up_messages` rows the scheduler will later dispatch. Each row
   carries a full recipient snapshot (`contact_name` / `contact_phone` /
   `contact_email`) so a later Contacts overwrite cannot rewrite the history
   of an already-scheduled send (Section-3 replace-semantics safety).

2. `dispatch_due(...)` — called by the AsyncIOScheduler tick every minute.
   Atomically flips each due row from `scheduled` → `dispatching`, checks the
   hub is still eligible (`status == "active"` — paused if paid/disputed),
   sends via the WhatsApp provider, mirrors an outbound row into
   `whatsapp_messages`, and finalises the row to `sent` / `failed` / `skipped`.

Cadence (from `due_date`, dispatched at 09:00 UTC on the target day):
    day 3   : POC follow_up
    day 7   : POC follow_up
    day 14  : escalation_1 escalation (fallback: POC follow_up if no esc-1)
    day 30  : escalation_1 escalation (fallback: POC follow_up if no esc-1)
Message 1 (initial, POC) is created and sent inside `approve_plan` before this
module is called, so the plan is a "5-message" plan end-to-end.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from ..providers.whatsapp import provider as wa_provider
from ..repositories import store
from ..services import templates as tmpl
from ..util import iso, new_id

logger = logging.getLogger("dueo.follow_ups")

# (days_after_due, contact_role, template_category). Kept as a module constant
# so the scheduler tests can assert on this list directly.
SCHEDULE: list[tuple[int, str, str]] = [
    (3, "poc", "follow_up"),
    (7, "poc", "follow_up"),
    (14, "escalation_1", "escalation"),
    (30, "escalation_1", "escalation"),
]


def _at_9am_utc(day: str, offset_days: int) -> str:
    """Take a YYYY-MM-DD due date and return an ISO-8601 UTC timestamp for
    09:00 UTC (~14:30 IST) `offset_days` after it. Falls back to "now +
    offset" when the due date is unparseable so scheduling never crashes."""
    try:
        base = datetime.strptime(day, "%Y-%m-%d").replace(
            hour=9, minute=0, tzinfo=timezone.utc,
        )
    except (TypeError, ValueError):
        base = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    return (base + timedelta(days=offset_days)).isoformat()


def build_scheduled_rows(
    *,
    hub: dict,
    plan_id: str,
    tone: str,
    poc: dict,
    esc1: Optional[dict],
    business_name: str,
    public_base: str,
) -> list[dict]:
    """Render + snapshot the 4 scheduled follow-up rows for this hub. No DB
    writes here — the caller inserts them in one shot inside `approve_plan`."""
    rows: list[dict] = []
    now = iso()
    due = hub.get("due_date")
    for offset, role, category in SCHEDULE:
        contact = esc1 if role == "escalation_1" and esc1 else poc
        effective_category = category if (role == "escalation_1" and esc1) else "follow_up"
        body = tmpl.render(
            tone, effective_category, hub, poc, esc1, business_name, public_base,
        )
        rows.append({
            "id": new_id(),
            "payment_hub_id": hub["id"],
            "plan_id": plan_id,
            "contact_role": "escalation_1" if (role == "escalation_1" and esc1) else "poc",
            "contact_name": contact["name"],
            "contact_phone": contact["phone"],
            "contact_email": contact["email"],
            "channel": "whatsapp",
            "category": effective_category,
            "body": body,
            "status": "scheduled",
            "scheduled_for": _at_9am_utc(due, offset),
            "sent_at": None,
            "created_at": now,
        })
    return rows


async def dispatch_due(now_iso: Optional[str] = None, limit: int = 50) -> dict:
    """Scheduler tick body. Claims each due row atomically, dispatches, and
    writes back the final state. Safe to invoke concurrently — the atomic
    claim on `follow_up_messages` guarantees a row cannot be sent twice.

    Returns a summary dict for observability tests."""
    cutoff = now_iso or iso()
    sent = failed = skipped = 0
    while sent + failed + skipped < limit:
        claimed = await store.claim_scheduled_follow_up(cutoff)
        if not claimed:
            break
        hub = await store.get_payment_hub(claimed["payment_hub_id"])
        if not hub or hub.get("status") != "active":
            await store.update_follow_up_message(claimed["id"], {
                "status": "skipped",
                "skip_reason": f"hub_status={hub.get('status') if hub else 'missing'}",
                "updated_at": iso(),
            })
            skipped += 1
            continue
        try:
            result = await wa_provider.send_freeform(claimed["contact_phone"], claimed["body"])
            await store.insert_whatsapp_message({
                "id": new_id(),
                "provider_sid": result.provider_id,
                "direction": "outbound",
                "channel": "whatsapp",
                "from_addr": None,
                "to_addr": claimed["contact_phone"],
                "to_name": claimed["contact_name"],
                "body": claimed["body"],
                "num_media": 0,
                "status": result.status,
                "payment_hub_id": hub["id"],
                "org_id": hub["org_id"],
                "created_at": iso(),
            })
            await store.update_follow_up_message(claimed["id"], {
                "status": "sent",
                "sent_at": iso(),
                "provider_sid": result.provider_id,
                "provider_status": result.status,
            })
            sent += 1
        except Exception as e:  # noqa: BLE001
            err = str(e)[:400]
            logger.warning("follow_up dispatch failed msg=%s: %s", claimed["id"], err)
            await store.update_follow_up_message(claimed["id"], {
                "status": "failed",
                "error": err,
                "updated_at": iso(),
            })
            failed += 1
    return {"sent": sent, "failed": failed, "skipped": skipped, "cutoff": cutoff}
