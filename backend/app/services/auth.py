"""Passwordless email-OTP login, sessions, and invite-link consumption."""
import asyncio
from datetime import timedelta

from ..config import settings
from ..providers import email as email_provider
from ..repositories import store
from ..util import (
    compare_digest,
    gen_code,
    gen_token,
    hash_secret,
    iso,
    new_id,
    utcnow,
)
from . import audit

OTP_TTL_MIN = 10
OTP_MAX_ATTEMPTS = 5
OTP_LOCK_MIN = 15
SESSION_TTL_DAYS = 30

NEUTRAL_MESSAGE = "If this email has access, we've sent a sign-in code."


def _base_url() -> str:
    return settings.APP_URL.rstrip("/")


async def request_code(email: str, ip: str) -> dict:
    """Always returns the neutral message with an equalised timing profile."""
    email_count = await store.rate_incr("otp_email", email, 900)
    ip_count = await store.rate_incr("otp_ip", ip, 900)
    user = await store.get_user_by_email(email)
    allowed = email_count <= 5 and ip_count <= 40 and user and user.get("status") == "active"
    if allowed:
        code = gen_code()
        await store.deactivate_otps(email)
        await store.insert_otp(
            {
                "id": new_id(),
                "email": email,
                "digest": hash_secret(code),
                "expires_at": utcnow() + timedelta(minutes=OTP_TTL_MIN),
                "attempts": 0,
                "locked_until": None,
                "active": True,
                "created_at": iso(),
            }
        )
        subject = "Your Dueo sign-in code"
        html = (
            f'<table role="presentation" width="100%"><tr><td style="padding:24px;'
            f'font-family:Arial,sans-serif;color:#16130F">'
            f"<p>Your Dueo sign-in code is <strong>{code}</strong>. It expires in 10 minutes.</p>"
            f'<p style="font-size:12px;color:#888">Sent by Dueo. We never ask for your '
            f"password or codes by email reply.</p></td></tr></table>"
        )
        await email_provider.send_email(to=email, subject=subject, html=html, kind="login_code")
    else:
        await asyncio.sleep(0.05)  # equalise timing for unknown/blocked emails
    return {"message": NEUTRAL_MESSAGE}


async def new_session(user_id: str) -> str:
    raw = gen_token(32)
    await store.insert_session(
        {
            "id": new_id(),
            "user_id": user_id,
            "digest": hash_secret(raw),
            "expires_at": utcnow() + timedelta(days=SESSION_TTL_DAYS),
            "created_at": iso(),
        }
    )
    return raw


async def verify_code(email: str, code: str, ip: str) -> dict:
    ip_count = await store.rate_incr("verify_ip", ip, 900)
    if ip_count > 60:
        raise ValueError("rate_limited")
    otp = await store.get_active_otp(email)
    t = utcnow()

    def _aware(dt):
        if dt is not None and dt.tzinfo is None:
            from datetime import timezone as _tz

            return dt.replace(tzinfo=_tz.utc)
        return dt

    def _fail():
        raise ValueError("invalid_code")

    if not otp:
        await audit.append_event("login_failed", email, {"reason": "no_code"})
        _fail()
    locked = _aware(otp.get("locked_until"))
    if (locked and locked > t) or _aware(otp["expires_at"]) <= t:
        await audit.append_event("login_failed", email, {"reason": "expired_or_locked"})
        _fail()
    if not compare_digest(otp["digest"], hash_secret(code)):
        attempts = otp["attempts"] + 1
        lock = (t + timedelta(minutes=OTP_LOCK_MIN)) if attempts >= OTP_MAX_ATTEMPTS else None
        await store.bump_otp_attempts(otp["id"], lock)
        await audit.append_event("login_failed", email, {"reason": "wrong_code"})
        _fail()
    consumed = await store.consume_otp(otp["id"])
    if not consumed:
        _fail()
    user = await store.get_user_by_email(email)
    if not user or user.get("status") != "active":
        await audit.append_event("login_failed", email, {"reason": "inactive"})
        raise ValueError("account_unavailable")
    token = await new_session(user["id"])
    await audit.append_event("login_succeeded", email, {"user_id": user["id"]})
    return {"token": token, "user": user}


async def logout(raw_token: str | None):
    if raw_token:
        await store.delete_session_by_digest(hash_secret(raw_token))


async def session_user(raw_token: str | None):
    if not raw_token:
        return None
    sess = await store.get_session_by_digest(hash_secret(raw_token))
    if not sess:
        return None
    user = await store.get_user(sess["user_id"])
    if not user or user.get("status") != "active":
        await store.delete_session_by_digest(hash_secret(raw_token))
        return None
    return user
