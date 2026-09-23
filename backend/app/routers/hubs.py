"""Invoice + payment-hub routes for the authenticated business user. A
`payment_hub` is Dueo's unit of work: one invoice we are following up on. This
router turns an already-uploaded PDF/image into a draft hub, running the LLM
extract when the upload is an image (PDFs go through to Review with empty
fields until we add PDF-to-image conversion)."""
import asyncio
import base64
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..deps import current_context
from ..providers import storage
from ..providers.llm import llm_provider
from ..repositories import store
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
