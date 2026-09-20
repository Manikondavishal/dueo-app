"""Authenticated tenant-space routes: setup and context."""
from fastapi import APIRouter, Depends, HTTPException

from ..deps import current_context
from ..models import SetupIn
from ..services import org as org_service

router = APIRouter(prefix="/api/app")


@router.get("/context")
async def context(ctx=Depends(current_context)):
    return {"user": ctx["user"], "org": ctx["org"], "role": ctx["role"]}


@router.post("/setup")
async def setup(body: SetupIn, ctx=Depends(current_context)):
    try:
        updated = await org_service.complete_setup(ctx["org_id"], ctx["user"]["email"], body)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"org": updated}
