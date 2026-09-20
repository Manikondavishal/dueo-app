"""File upload (auth) + download (auth, org-scoped) via Emergent object storage."""
import asyncio
import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import Response

from ..deps import current_context
from ..providers import storage
from ..repositories import store
from ..util import iso, new_id

router = APIRouter(prefix="/api/uploads")

ALLOWED = {"application/pdf", "image/png", "image/jpeg", "image/webp"}
MAX_BYTES = 15 * 1024 * 1024


@router.post("")
async def upload(file: UploadFile, ctx=Depends(current_context)):
    if file.content_type not in ALLOWED:
        raise HTTPException(status_code=400, detail="unsupported_type")
    data = await file.read()
    if len(data) > MAX_BYTES:
        raise HTTPException(status_code=400, detail="file_too_large")
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in (file.filename or "") else "bin"
    path = f"{storage.APP_NAME}/uploads/{ctx['org_id']}/{uuid.uuid4()}.{ext}"
    try:
        result = await asyncio.to_thread(storage.put_object, path, data, file.content_type)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"storage_error: {str(e)[:150]}")
    upload_id = new_id()
    await store.insert_upload(
        {
            "id": upload_id,
            "org_id": ctx["org_id"],
            "filename": file.filename,
            "content_type": file.content_type,
            "size": result.get("size", len(data)),
            "storage_path": result["path"],
            "created_at": iso(),
        }
    )
    return {"id": upload_id, "filename": file.filename, "size": result.get("size", len(data))}


@router.get("/{upload_id}")
async def download(upload_id: str, ctx=Depends(current_context)):
    doc = await store.get_upload(ctx["org_id"], upload_id)
    if not doc:
        raise HTTPException(status_code=404, detail="not_found")
    try:
        data, ctype = await asyncio.to_thread(storage.get_object, doc["storage_path"])
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"storage_error: {str(e)[:150]}")
    return Response(
        content=data,
        media_type=doc.get("content_type", ctype),
        headers={"Content-Disposition": f'inline; filename="{doc["filename"]}"'},
    )
