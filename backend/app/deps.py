"""FastAPI dependencies: session user, tenant context, admin guard, client IP."""
from fastapi import Depends, HTTPException, Request

from .config import settings
from .repositories import store
from .services import auth
from .util import norm_email

SESSION_COOKIE = "dueo_session"


def client_ip(request: Request) -> str:
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "0.0.0.0"


async def current_user(request: Request) -> dict:
    user = await auth.session_user(request.cookies.get(SESSION_COOKIE))
    if not user:
        raise HTTPException(status_code=401, detail="not_authenticated")
    return user


async def current_context(user: dict = Depends(current_user)) -> dict:
    membership = await store.get_membership_for_user(user["id"])
    if not membership:
        raise HTTPException(status_code=403, detail="no_organization")
    org = await store.get_org(membership["org_id"])
    if not org:
        raise HTTPException(status_code=404, detail="org_not_found")
    return {"user": user, "org": org, "org_id": org["id"], "role": membership["role"]}


async def require_admin(user: dict = Depends(current_user)) -> dict:
    if norm_email(user["email"]) not in settings.admin_emails:
        raise HTTPException(status_code=403, detail="forbidden")
    return user
