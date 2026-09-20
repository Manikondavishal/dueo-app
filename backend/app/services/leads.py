"""Waitlist leads: public submission, admin decisions, invite issuance & consumption."""
from datetime import timedelta

from ..config import settings
from ..models import AUTO_REVIEW_TYPES
from ..providers import email as email_provider
from ..repositories import store
from ..util import gen_token, hash_secret, iso, new_id, utcnow, valid_email
from . import audit, auth

CONFIRM_MESSAGE = "Thanks for requesting an invite. We review every request by hand."
INVITE_TTL_DAYS = 7


def _base_url() -> str:
    return settings.APP_URL.rstrip("/")


# ---------------------------------------------------------------------------
# Public submission
# ---------------------------------------------------------------------------
async def submit_lead(data, ip: str) -> dict:
    # Honeypot: silently accept, store nothing.
    if data.company_website.strip():
        return {"message": CONFIRM_MESSAGE}
    if not valid_email(data.work_email):
        raise ValueError("invalid_email")
    count = await store.rate_incr("invite_ip", ip, 3600)
    if count > 5:
        raise ValueError("rate_limited")
    existing = await store.get_lead_by_email(data.work_email)
    if existing:
        return {"message": CONFIRM_MESSAGE}  # idempotent — same success
    status = "new" if data.business_type in AUTO_REVIEW_TYPES else "manual_review"
    lead = {
        "id": new_id(),
        "full_name": data.full_name.strip(),
        "business_name": data.business_name.strip(),
        "work_email": data.work_email,
        "mobile": data.mobile.strip(),
        "business_type": data.business_type,
        "city_state": data.city_state.strip(),
        "monthly_invoice_volume": data.monthly_invoice_volume.strip(),
        "udyam_number": (data.udyam_number or "").strip() or None,
        "status": status,
        "invite_token_hash": None,
        "invite_expires_at": None,
        "invite_sent_at": None,
        "invite_reminder_sent": False,
        "ip_hash": None,
        "created_at": iso(),
    }
    from ..util import hash_ip

    lead["ip_hash"] = hash_ip(ip)
    await store.insert_lead(lead)
    await audit.append_event("lead_created", data.work_email, {"lead_id": lead["id"], "status": status})
    subject = "We received your Dueo invite request"
    html = (
        f'<table role="presentation" width="100%"><tr><td style="padding:24px;'
        f'font-family:Arial,sans-serif;color:#16130F">'
        f"<p>Thanks {_esc(data.full_name)}. We review every request by hand and will email "
        f"you when your invite is approved.</p>"
        f'<p style="font-size:12px;color:#888">Sent by Dueo.</p></td></tr></table>'
    )
    await email_provider.send_email(to=data.work_email, subject=subject, html=html, kind="lead_confirmation")
    return {"message": CONFIRM_MESSAGE}


def _esc(s: str) -> str:
    from html import escape

    return escape(s or "")


async def _issue_invite(lead: dict) -> dict:
    token = gen_token(32)
    fields = {
        "status": "approved",
        "invite_token_hash": hash_secret(token),
        "invite_expires_at": iso(utcnow() + timedelta(days=INVITE_TTL_DAYS)),
        "invite_sent_at": iso(),
        "invite_reminder_sent": False,
    }
    lead = await store.update_lead(lead["id"], fields)
    link = f"{_base_url()}/invite?token={token}"
    subject = "Your Dueo invite is approved"
    html = (
        f'<table role="presentation" width="100%"><tr><td style="padding:24px;'
        f'font-family:Arial,sans-serif;color:#16130F">'
        f"<p>Your invite is approved. Sign in here: "
        f'<a href="{link}">{link}</a>.</p>'
        f"<p>It works once and expires in 7 days.</p>"
        f'<p style="font-size:12px;color:#888">Sent by Dueo.</p></td></tr></table>'
    )
    await email_provider.send_email(to=lead["work_email"], subject=subject, html=html, kind="invite")
    return lead


# ---------------------------------------------------------------------------
# Admin decisions
# ---------------------------------------------------------------------------
async def admin_action(lead_id: str, action: str, actor: str, note: str = "") -> dict:
    lead = await store.get_lead(lead_id)
    if not lead:
        raise ValueError("not_found")
    if action == "approve":
        lead = await _issue_invite(lead)
        await audit.append_event("lead_approved", actor, {"lead_id": lead_id})
    elif action == "hold":
        lead = await store.update_lead(lead_id, {"status": "held", "review_note": note})
        await audit.append_event("lead_held", actor, {"lead_id": lead_id, "note": note})
    elif action == "reject":
        lead = await store.update_lead(lead_id, {"status": "rejected", "review_note": note})
        await audit.append_event("lead_rejected", actor, {"lead_id": lead_id, "note": note})
    elif action == "resend":
        lead = await _issue_invite(lead)
    else:
        raise ValueError("bad_action")
    return lead


# ---------------------------------------------------------------------------
# Invite consumption (verifies email, creates user + org, opens setup)
# ---------------------------------------------------------------------------
async def consume_invite(token: str) -> dict:
    token_hash = hash_secret(token)
    lead = await store.get_lead_by_invite_hash(token_hash)
    if not lead:
        raise ValueError("invalid_link")
    if lead["status"] not in ("approved", "activated"):
        raise ValueError("invalid_link")
    expires = lead.get("invite_expires_at")
    if not expires or expires < iso():
        raise ValueError("invalid_link")

    user = await store.get_user_by_email(lead["work_email"])
    org = None
    if lead["status"] == "activated" and user:
        # Link already used — per spec this must be rejected.
        raise ValueError("invalid_link")

    user = {
        "id": new_id(),
        "email": lead["work_email"],
        "full_name": lead["full_name"],
        "mobile": lead["mobile"],
        "status": "active",
        "created_at": iso(),
    }
    await store.insert_user(user)
    org = {
        "id": new_id(),
        "display_name": lead["business_name"],
        "timezone": "Asia/Kolkata",
        "country": "IN",
        "currency": "INR",
        "udyam_number": lead.get("udyam_number"),
        "settings": {"setup_completed": False, "setup_step": 1},
        "created_at": iso(),
    }
    await store.insert_org(org)
    if await store.count_members(org["id"]) >= settings.MAX_MEMBERS_PER_ORG:
        raise ValueError("org_full")
    await store.insert_member(
        {
            "id": new_id(),
            "org_id": org["id"],
            "user_id": user["id"],
            "role": "owner",
            "status": "active",
            "created_at": iso(),
        }
    )
    await store.update_lead(
        lead["id"], {"status": "activated", "invite_token_hash": None, "activated_at": iso()}
    )
    await audit.append_event("invite_used", user["email"], {"lead_id": lead["id"]}, chain_key=org["id"])
    await audit.append_event("org_created", user["email"], {"org_id": org["id"]}, chain_key=org["id"])
    token = await auth.new_session(user["id"])
    return {"token": token, "user": user, "org": org}


async def send_day5_reminders() -> int:
    cutoff = iso(utcnow() - timedelta(days=5))
    leads = await store.list_leads_pending_reminder(cutoff)
    sent = 0
    for lead in leads:
        if lead.get("status") != "approved":
            continue
        link_note = "Your Dueo invite is still waiting."
        subject = "Reminder: your Dueo invite is waiting"
        html = (
            f'<table role="presentation" width="100%"><tr><td style="padding:24px;'
            f'font-family:Arial,sans-serif;color:#16130F"><p>{link_note} '
            f"Check the approval email we sent you to sign in. The link expires 7 days after approval.</p>"
            f'<p style="font-size:12px;color:#888">Sent by Dueo.</p></td></tr></table>'
        )
        await email_provider.send_email(to=lead["work_email"], subject=subject, html=html, kind="invite_reminder")
        await store.update_lead(lead["id"], {"invite_reminder_sent": True})
        sent += 1
    return sent
