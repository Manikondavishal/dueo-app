"""Platform-admin routes. Guarded by ADMIN_EMAILS membership."""
from fastapi import APIRouter, Depends, HTTPException

from ..deps import require_admin
from ..models import LeadActionIn
from ..repositories import store
from ..services import audit, leads, org

router = APIRouter(prefix="/api/admin")


@router.get("/leads")
async def list_leads(status: str | None = None, _admin=Depends(require_admin)):
    return {"leads": await store.list_leads(status)}


@router.post("/leads/{lead_id}/action")
async def lead_action(lead_id: str, body: LeadActionIn, admin=Depends(require_admin)):
    try:
        lead = await leads.admin_action(lead_id, body.action, admin["email"], body.note)
    except ValueError as e:
        raise HTTPException(status_code=404 if str(e) == "not_found" else 400, detail=str(e))
    return {"lead": lead}


@router.get("/users")
async def list_users(_admin=Depends(require_admin)):
    return {"users": await store.list_users()}


@router.post("/users/{user_id}/suspend")
async def suspend(user_id: str, admin=Depends(require_admin)):
    await org.suspend_user(user_id, admin["email"])
    return {"ok": True}


@router.post("/users/{user_id}/restore")
async def restore(user_id: str, admin=Depends(require_admin)):
    await org.restore_user(user_id, admin["email"])
    return {"ok": True}


@router.get("/outbox")
async def outbox(_admin=Depends(require_admin)):
    return {"emails": await store.list_outbox()}


@router.get("/audit/verify")
async def audit_verify(chain_key: str = "platform", _admin=Depends(require_admin)):
    return await audit.verify_audit_chain(chain_key)
