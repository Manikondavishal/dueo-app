"""Phase-0 developer endpoints: LLM image->JSON and scheduler evidence."""
from fastapi import APIRouter, Depends, HTTPException

from ..deps import require_admin
from ..providers.llm import llm_provider
from ..repositories import store

router = APIRouter(prefix="/api/dev")


@router.post("/llm-extract")
async def llm_extract(body: dict, _admin=Depends(require_admin)):
    image_b64 = (body or {}).get("image_base64")
    if not image_b64:
        raise HTTPException(status_code=400, detail="image_base64_required")
    instruction = (body or {}).get(
        "instruction",
        "Extract invoice fields as JSON with keys: invoice_number, client_name, "
        "amount, currency, due_date. Use null when a field is not present.",
    )
    try:
        data = await llm_provider.extract_json_from_image(image_b64, instruction)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"llm_error: {str(e)[:200]}")
    return {"structured": data}


@router.get("/scheduler-runs")
async def scheduler_runs(_admin=Depends(require_admin)):
    return {"runs": await store.last_runs(10), "webhook_events": await store.count_webhook_events()}
