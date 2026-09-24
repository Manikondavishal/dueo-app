"""In-app scheduler (explicitly required by the pilot spec).

- every minute: a tick enqueues a heartbeat job, a worker atomically claims it.
- daily 00:10 Asia/Kolkata: store a digest of every audit chain head.
"""
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from ..repositories import store
from ..services import audit, follow_ups
from ..util import canonical_json, iso, new_id, sha256_hex

logger = logging.getLogger("dueo.scheduler")
_scheduler: AsyncIOScheduler | None = None


async def scheduler_tick(worker_id: str = "scheduler-1") -> dict | None:
    await store.enqueue_job({"id": new_id(), "type": "heartbeat", "status": "pending", "created_at": iso()})
    claimed = await store.claim_pending_job(worker_id)
    if not claimed:
        return None
    await store.complete_job(claimed["id"])
    # Dispatch any follow-up messages whose scheduled_for has arrived. Wrapped
    # so a bad row can never crash the heartbeat run.
    try:
        summary = await follow_ups.dispatch_due()
        if summary["sent"] or summary["failed"] or summary["skipped"]:
            logger.info("follow_ups dispatched %s", summary)
    except Exception as e:  # noqa: BLE001
        logger.error("follow_ups dispatch crashed: %s", str(e)[:300])
    run = {"id": new_id(), "job_id": claimed["id"], "worker": worker_id, "at": iso()}
    await store.record_run(run)
    return run


async def daily_audit_anchor() -> dict:
    keys = await store.all_chain_keys()
    heads = {}
    for k in keys:
        head = await store.get_audit_head(k)
        heads[k] = head["hash"] if head else None
    digest = sha256_hex(canonical_json(heads))
    doc = {"id": new_id(), "at": iso(), "heads": heads, "digest": digest}
    await store.insert_audit_anchor(doc)
    return doc


def start_scheduler():
    global _scheduler
    if _scheduler:
        return
    _scheduler = AsyncIOScheduler(timezone="UTC")
    _scheduler.add_job(scheduler_tick, CronTrigger(minute="*"), id="tick", replace_existing=True)
    _scheduler.add_job(
        daily_audit_anchor,
        CronTrigger(hour=0, minute=10, timezone="Asia/Kolkata"),
        id="daily_anchor",
        replace_existing=True,
    )
    _scheduler.start()
    logger.info("scheduler started")


def stop_scheduler():
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None
