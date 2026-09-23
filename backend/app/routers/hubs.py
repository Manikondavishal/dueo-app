"""Invoice + payment-hub routes for the authenticated business user. A
`payment_hub` is Dueo's unit of work: one invoice we are following up on. This
router turns an already-uploaded PDF/image into a draft hub, running the LLM
extract when the upload is an image (PDFs go through to Review with empty
fields until we add PDF-to-image conversion)."""
import asyncio
import base64
import logging
import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..deps import current_context
from ..providers import storage
from ..providers.llm import llm_provider
from ..providers.whatsapp import provider as wa_provider
from ..repositories import store
from ..services import templates as tmpl
from ..util import gen_token, iso, new_id

logger = logging.getLogger("dueo.hubs")

router = APIRouter(prefix="/api/hubs")


class FromUploadIn(BaseModel):
    upload_id: str = Field(min_length=1)


class PatchHubIn(BaseModel):
    invoice_number: str | None = Field(default=None, max_length=80)
    client_name: str | None = Field(default=None, max_length=200)
    amount_rupees: float | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, max_length=8)
    due_date: str | None = Field(default=None, max_length=32)
    business_payment_details: str | None = Field(default=None, max_length=2000)


class HandlingIn(BaseModel):
    mode: str  # "share_myself" | "dueo_handles"


class ContactIn(BaseModel):
    name: str = Field(default="", max_length=120)
    phone: str = Field(default="", max_length=32)
    email: str = Field(default="", max_length=200)


class ContactsIn(BaseModel):
    poc: ContactIn
    escalation_1: ContactIn | None = None
    escalation_2: ContactIn | None = None


class ApproveIn(BaseModel):
    tone: str  # "professional" | "warm" | "firm"
    consent: bool = False


def _to_paise(amount) -> int | None:
    """Coerce the LLM's `amount` field (could be int, float, or numeric string
    with commas / rupee sign) into integer paise. Returns None on any failure."""
    if amount is None:
        return None
    try:
        s = str(amount).replace(",", "").replace("\u20B9", "").replace("Rs", "").strip()
        return int(round(float(s) * 100))
    except Exception:  # noqa: BLE001
        return None


EXTRACT_INSTRUCTION = (
    "Extract the following fields from this Indian invoice and return them "
    "as a single JSON object with exactly these keys (use null when a field "
    "is not clearly present): "
    "invoice_number (string), client_name (the company being billed, string), "
    "amount (number in rupees, no currency symbol), currency (always 'INR'), "
    "due_date (YYYY-MM-DD)."
)


@router.post("/from-upload")
async def create_hub_from_upload(body: FromUploadIn, ctx=Depends(current_context)):
    upload = await store.get_upload(ctx["org_id"], body.upload_id)
    if not upload:
        raise HTTPException(status_code=404, detail="upload_not_found")

    extracted: dict = {}
    llm_status = "skipped"
    if (upload.get("content_type") or "").startswith("image/"):
        try:
            data, _ct = await asyncio.to_thread(storage.get_object, upload["storage_path"])
            b64 = base64.b64encode(data).decode()
            extracted = await llm_provider.extract_json_from_image(b64, EXTRACT_INSTRUCTION)
            llm_status = "ok"
        except Exception as e:  # noqa: BLE001
            logger.warning("hub extract failed: %s", str(e)[:200])
            llm_status = "failed"

    hub_id = new_id()
    hub = {
        "id": hub_id,
        "org_id": ctx["org_id"],
        "upload_id": upload["id"],
        "public_token": gen_token(24),
        "invoice_number": (extracted.get("invoice_number") or "") or None,
        "client_name": (extracted.get("client_name") or "") or None,
        "amount_paise": _to_paise(extracted.get("amount")),
        "currency": (extracted.get("currency") or "INR") or "INR",
        "due_date": (extracted.get("due_date") or "") or None,
        "business_payment_details": "",
        "status": "draft",
        "llm_status": llm_status,
        "created_at": iso(),
        "created_by": ctx["user"]["id"],
    }
    await store.insert_payment_hub(hub)
    return {"hub": hub, "extracted": extracted, "llm_status": llm_status}


@router.get("/{hub_id}")
async def read_hub(hub_id: str, ctx=Depends(current_context)):
    hub = await store.get_payment_hub(hub_id)
    if not hub or hub.get("org_id") != ctx["org_id"]:
        raise HTTPException(status_code=404, detail="not_found")
    return {"hub": hub}


@router.patch("/{hub_id}")
async def patch_hub(hub_id: str, body: PatchHubIn, ctx=Depends(current_context)):
    """Editable while the hub is still a draft. Once a follow-up plan has been
    approved (Section 4) the hub is locked from field edits."""
    hub = await store.get_payment_hub(hub_id)
    if not hub or hub.get("org_id") != ctx["org_id"]:
        raise HTTPException(status_code=404, detail="not_found")
    if hub.get("status") != "draft":
        raise HTTPException(status_code=409, detail="hub_not_draft")

    updates: dict = {}
    data = body.model_dump(exclude_unset=True)
    if "amount_rupees" in data:
        v = data.pop("amount_rupees")
        updates["amount_paise"] = None if v is None else int(round(v * 100))
    for k in ("invoice_number", "client_name", "currency", "due_date", "business_payment_details"):
        if k in data:
            val = data[k]
            updates[k] = (val.strip() if isinstance(val, str) else val) or None
    updates["updated_at"] = iso()

    updated = await store.update_payment_hub(hub_id, updates)
    return {"hub": updated}


@router.get("")
async def list_hubs(ctx=Depends(current_context)):
    return {"hubs": await store.list_payment_hubs_for_org(ctx["org_id"])}


@router.post("/{hub_id}/handling")
async def set_handling(hub_id: str, body: HandlingIn, ctx=Depends(current_context)):
    """Section 2: record whether the owner will share the link themselves or let
    Dueo do the follow-up. Only settable while the hub is a draft."""
    if body.mode not in ("share_myself", "dueo_handles"):
        raise HTTPException(status_code=400, detail="invalid_mode")
    hub = await store.get_payment_hub(hub_id)
    if not hub or hub.get("org_id") != ctx["org_id"]:
        raise HTTPException(status_code=404, detail="not_found")
    if hub.get("status") != "draft":
        raise HTTPException(status_code=409, detail="hub_not_draft")
    updated = await store.update_payment_hub(hub_id, {"handling_mode": body.mode, "updated_at": iso()})
    return {"hub": updated}


_PHONE_RE = re.compile(r"^\+?\d[\d\s\-]{6,}$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _validate_contact(c: "ContactIn", who: str, required: bool) -> dict | None:
    name = (c.name or "").strip()
    phone = (c.phone or "").strip()
    email = (c.email or "").strip().lower()
    filled = any([name, phone, email])
    if not filled and not required:
        return None
    missing = [k for k, v in (("name", name), ("phone", phone), ("email", email)) if not v]
    if missing:
        raise HTTPException(status_code=400, detail=f"{who}_missing_{missing[0]}")
    if not _PHONE_RE.match(phone):
        raise HTTPException(status_code=400, detail=f"{who}_bad_phone")
    if not _EMAIL_RE.match(email):
        raise HTTPException(status_code=400, detail=f"{who}_bad_email")
    return {"name": name, "phone": phone, "email": email}


@router.get("/{hub_id}/contacts")
async def read_hub_contacts(hub_id: str, ctx=Depends(current_context)):
    hub = await store.get_payment_hub(hub_id)
    if not hub or hub.get("org_id") != ctx["org_id"]:
        raise HTTPException(status_code=404, detail="not_found")
    return {"contacts": await store.list_hub_contacts(hub_id)}


@router.post("/{hub_id}/contacts")
async def save_hub_contacts(hub_id: str, body: ContactsIn, ctx=Depends(current_context)):
    """Section 3: replace the contact set for this hub. Primary is required
    (name+phone+email); escalations are optional but if partially filled must
    be fully valid. Idempotent — re-submitting rewrites the set."""
    hub = await store.get_payment_hub(hub_id)
    if not hub or hub.get("org_id") != ctx["org_id"]:
        raise HTTPException(status_code=404, detail="not_found")
    if hub.get("status") != "draft":
        raise HTTPException(status_code=409, detail="hub_not_draft")

    parts = [
        ("poc", body.poc, True),
        ("escalation_1", body.escalation_1 or ContactIn(), False),
        ("escalation_2", body.escalation_2 or ContactIn(), False),
    ]
    rows: list[dict] = []
    for role, c, required in parts:
        got = _validate_contact(c, role, required)
        if got is None:
            continue
        rows.append({
            "id": new_id(),
            "payment_hub_id": hub_id,
            "role": role,
            **got,
            "created_at": iso(),
        })
    saved = await store.replace_hub_contacts(hub_id, rows)
    return {"contacts": saved}


# --- Section 4: Tone & Approve ------------------------------------------------

async def _render_all(tone: str, hub: dict, contacts: list[dict], business_name: str) -> dict:
    from ..config import settings
    poc = next((c for c in contacts if c["role"] == "poc"), None)
    esc = next((c for c in contacts if c["role"] == "escalation_1"), None)
    base = (settings.APP_URL or "").rstrip("/")
    return {
        cat: tmpl.render(tone, cat, hub, poc, esc, business_name, base)
        for cat in tmpl.CATEGORIES
    }


@router.get("/{hub_id}/preview-messages")
async def preview_messages(hub_id: str, tone: str = "professional",
                           ctx=Depends(current_context)):
    if tone not in tmpl.TONES:
        raise HTTPException(status_code=400, detail="bad_tone")
    hub = await store.get_payment_hub(hub_id)
    if not hub or hub.get("org_id") != ctx["org_id"]:
        raise HTTPException(status_code=404, detail="not_found")
    contacts = await store.list_hub_contacts(hub_id)
    return {"tone": tone, "messages": await _render_all(tone, hub, contacts, ctx["org"]["display_name"])}


@router.post("/{hub_id}/approve")
async def approve_plan(hub_id: str, body: ApproveIn, ctx=Depends(current_context)):
    """Section 4: create the follow_up_plan (status=approved), render + persist
    the first follow_up_message (category=initial, status=scheduled), then
    dispatch it via the WhatsAppProvider to the primary contact. If the send
    succeeds the message flips to `sent`; on failure it goes to `failed` with
    the error preserved. The hub itself becomes `active` either way — the plan
    exists, retries can happen later."""
    if not body.consent:
        raise HTTPException(status_code=400, detail="consent_required")
    if body.tone not in tmpl.TONES:
        raise HTTPException(status_code=400, detail="bad_tone")

    hub = await store.get_payment_hub(hub_id)
    if not hub or hub.get("org_id") != ctx["org_id"]:
        raise HTTPException(status_code=404, detail="not_found")
    if hub.get("status") != "draft":
        raise HTTPException(status_code=409, detail="hub_not_draft")

    contacts = await store.list_hub_contacts(hub_id)
    poc = next((c for c in contacts if c["role"] == "poc"), None)
    if not poc:
        raise HTTPException(status_code=400, detail="no_primary_contact")

    business_name = ctx["org"]["display_name"]
    body_text = tmpl.render(body.tone, "initial", hub,
                            poc, next((c for c in contacts if c["role"] == "escalation_1"), None),
                            business_name, (ctx.get("app_url") or ""))

    now = iso()
    plan = await store.insert_follow_up_plan({
        "id": new_id(), "payment_hub_id": hub_id, "tone": body.tone,
        "status": "approved", "approved_at": now, "created_at": now,
        "approved_by": ctx["user"]["id"],
    })
    msg = await store.insert_follow_up_message({
        "id": new_id(), "payment_hub_id": hub_id, "plan_id": plan["id"],
        "contact_role": "poc", "channel": "whatsapp", "category": "initial",
        "body": body_text, "status": "scheduled", "scheduled_for": now,
        "sent_at": None, "created_at": now,
    })

    send_err = None
    try:
        sent = await wa_provider.send_freeform(poc["phone"], body_text)
        # Also persist a mirror row in whatsapp_messages so the conversation view
        # (Section 6) can render everything from one collection.
        await store.insert_whatsapp_message({
            "id": new_id(), "provider_sid": sent.provider_id,
            "direction": "outbound", "channel": "whatsapp",
            "from_addr": None, "to_addr": poc["phone"], "body": body_text,
            "num_media": 0, "status": sent.status, "payment_hub_id": hub_id,
            "org_id": ctx["org_id"], "created_at": iso(),
        })
        await store.update_follow_up_message(msg["id"], {
            "status": "sent", "sent_at": iso(),
            "provider_sid": sent.provider_id, "provider_status": sent.status,
        })
    except Exception as e:  # noqa: BLE001
        send_err = str(e)[:400]
        logger.warning("approve send failed: %s", send_err)
        await store.update_follow_up_message(msg["id"], {
            "status": "failed", "error": send_err,
        })

    await store.update_payment_hub(hub_id, {"status": "active", "updated_at": iso()})
    updated_msg = await store.list_follow_up_messages_for_hub(hub_id)
    return {
        "plan": plan,
        "message": updated_msg[0] if updated_msg else msg,
        "send_error": send_err,
    }
