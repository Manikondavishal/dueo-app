"""Manual dev script: forge a session for the phase0_upload user + create a
fresh draft payment_hub by uploading a synthetic invoice image. Used only to
speed up manual QA — /tmp scripts don't survive pod restarts, this one lives
inside /app so it does. Run from `/app/backend` so `app.*` imports resolve."""
import asyncio, io, json, os, sys
import httpx
from PIL import Image, ImageDraw, ImageFont
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")
sys.path.insert(0, "/app/backend")
from app.services import auth as auth_svc  # noqa: E402
from app.repositories import store, db as dbmod  # noqa: E402

APP_URL = os.environ.get("APP_URL_MANUAL", "https://invoice-follow-up-8.preview.emergentagent.com")


def render_invoice_png() -> bytes:
    img = Image.new("RGB", (900, 600), "white")
    d = ImageDraw.Draw(img)
    try:
        big = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 44)
        med = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 28)
        sm  = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 22)
    except Exception:
        big = med = sm = ImageFont.load_default()
    d.text((40, 30), "INVOICE", fill="black", font=big)
    d.text((40, 100), "Meridian Studio", fill="black", font=med)
    d.text((40, 160), "Bill to: Kestrel Logistics", fill="black", font=sm)
    d.text((40, 210), "Invoice #: INV-0417", fill="black", font=sm)
    d.text((40, 260), "Amount: Rs 85,000", fill="black", font=sm)
    d.text((40, 310), "Currency: INR", fill="black", font=sm)
    d.text((40, 360), "Due date: 2026-09-07", fill="black", font=sm)
    buf = io.BytesIO(); img.save(buf, "PNG"); return buf.getvalue()


async def main():
    c = AsyncIOMotorClient(os.environ["MONGO_URL"])
    d = c[os.environ["DB_NAME"]]
    store.db = d; dbmod.db = d

    user = await store.get_user_by_email("phase0_upload@example.com")
    raw = await auth_svc.new_session(user["id"])
    async with httpx.AsyncClient(base_url=APP_URL, cookies={"dueo_session": raw}, timeout=90) as h:
        r = await h.post("/api/uploads", files={"file": ("invoice.png", render_invoice_png(), "image/png")},
                         headers={"Origin": APP_URL})
        upload_id = r.json()["id"]
        r2 = await h.post("/api/hubs/from-upload", json={"upload_id": upload_id},
                          headers={"Origin": APP_URL})
        hub = r2.json()["hub"]

    with open("/app/scripts/last_session.txt", "w") as f: f.write(raw)
    with open("/app/scripts/last_hub_id.txt", "w") as f: f.write(hub["id"])
    print(json.dumps({"session_len": len(raw), "hub_id": hub["id"], "llm_status": hub.get("llm_status")}, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
