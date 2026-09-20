"""Organization setup (step 1 of 3) and admin user actions."""
from ..models import SetupIn
from ..repositories import store
from ..util import iso
from . import audit


async def complete_setup(org_id: str, actor: str, data: SetupIn) -> dict:
    if not data.consent:
        raise ValueError("consent_required")
    fields = {
        "display_name": data.display_name.strip(),
        "udyam_number": (data.udyam_number or "").strip() or None,
        "settings.setup_completed": True,
        "settings.setup_step": 1,
        "settings.owner_mobile": data.mobile.strip(),
        "settings.consent": {"version": data.consent_version, "at": iso()},
    }
    org = await store.update_org(org_id, fields)
    await audit.append_event("setup_completed", actor, {"org_id": org_id}, chain_key=org_id)
    return org


async def suspend_user(user_id: str, actor: str):
    await store.set_user_status(user_id, "suspended")
    await store.delete_sessions_for_user(user_id)  # revoke immediately
    await audit.append_event("user_suspended", actor, {"user_id": user_id})


async def restore_user(user_id: str, actor: str):
    await store.set_user_status(user_id, "active")
    await audit.append_event("user_suspended", actor, {"user_id": user_id, "restored": True})
