"""Auth: request OTP, verify, invite-link consume, me, logout."""
from fastapi import APIRouter, Depends, HTTPException, Request, Response

from ..deps import SESSION_COOKIE, client_ip, current_user
from ..models import EmailIn, VerifyIn
from ..services import auth, leads

router = APIRouter(prefix="/api/auth")

SESSION_MAX_AGE = 30 * 24 * 3600


def _set_cookie(response: Response, token: str):
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=SESSION_MAX_AGE,
        httponly=True,
        secure=True,
        samesite="lax",
        path="/",
    )


@router.post("/request-code")
async def request_code(body: EmailIn, request: Request):
    return await auth.request_code(body.email, client_ip(request))


@router.post("/verify")
async def verify(body: VerifyIn, request: Request, response: Response):
    try:
        result = await auth.verify_code(body.email, body.code, client_ip(request))
    except ValueError as e:
        reason = str(e)
        status = 429 if reason == "rate_limited" else (403 if reason == "account_unavailable" else 400)
        raise HTTPException(status_code=status, detail=reason)
    _set_cookie(response, result["token"])
    return {"ok": True, "user": result["user"]}


@router.post("/invite/consume")
async def consume_invite(request: Request, response: Response):
    body = await request.json()
    token = (body or {}).get("token", "")
    try:
        result = await leads.consume_invite(token)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="This link can't be used. Sign in with your email.",
        )
    _set_cookie(response, result["token"])
    return {"ok": True, "user": result["user"], "org": result["org"]}


@router.get("/me")
async def me(request: Request):
    from ..repositories import store

    user = await auth.session_user(request.cookies.get(SESSION_COOKIE))
    if not user:
        return {"authenticated": False}
    membership = await store.get_membership_for_user(user["id"])
    org = await store.get_org(membership["org_id"]) if membership else None
    from ..config import settings
    from ..util import norm_email

    return {
        "authenticated": True,
        "user": user,
        "org": org,
        "is_admin": norm_email(user["email"]) in settings.admin_emails,
    }


@router.post("/logout")
async def logout(request: Request, response: Response):
    await auth.logout(request.cookies.get(SESSION_COOKIE))
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"ok": True}
