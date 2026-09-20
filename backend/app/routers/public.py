"""Health + public invite (waitlist) submission."""
from fastapi import APIRouter, HTTPException, Request

from ..deps import client_ip
from ..models import InviteRequestIn
from ..services import leads

router = APIRouter(prefix="/api")


@router.get("/health")
async def health():
    return {"status": "ok", "service": "dueo", "pilot_country": "IN"}


@router.post("/invite/request")
async def request_invite(body: InviteRequestIn, request: Request):
    try:
        return await leads.submit_lead(body, client_ip(request))
    except ValueError as e:
        code = 429 if str(e) == "rate_limited" else 400
        raise HTTPException(status_code=code, detail=str(e))
