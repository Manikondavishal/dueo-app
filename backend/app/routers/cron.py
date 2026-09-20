"""Platform cron endpoints. Auth via Bearer WEBHOOK_CRON_SECRET; ack fast."""
import asyncio

from fastapi import APIRouter, Header, HTTPException

from ..config import settings
from ..jobs import scheduler
from ..services import leads
from ..util import compare_digest

router = APIRouter(prefix="/api/cron")


def _check(authorization: str | None):
    # Cron endpoints must ack 2xx immediately; enqueue/background the actual work.
    token = (authorization or "").removeprefix("Bearer ").strip()
    if not settings.WEBHOOK_CRON_SECRET or not compare_digest(token, settings.WEBHOOK_CRON_SECRET):
        raise HTTPException(status_code=401, detail="unauthorized")


@router.post("/tick")
async def cron_tick(authorization: str | None = Header(default=None)):
    _check(authorization)
    asyncio.create_task(scheduler.scheduler_tick("cron"))
    return {"accepted": True}


@router.post("/reminders")
async def cron_reminders(authorization: str | None = Header(default=None)):
    _check(authorization)
    asyncio.create_task(leads.send_day5_reminders())
    return {"accepted": True}


@router.post("/audit-anchor")
async def cron_anchor(authorization: str | None = Header(default=None)):
    _check(authorization)
    asyncio.create_task(scheduler.daily_audit_anchor())
    return {"accepted": True}
