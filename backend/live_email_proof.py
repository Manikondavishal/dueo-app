"""One-shot LIVE email proof through our own Resend key.

Seeds (idempotently) a Dueo user for the Resend account-owner address, then
runs the REAL `services.auth.request_code` path — same code the sign-in screen
hits — and prints the raw outcome plus the emails_outbox row. No fixtures, no
hardcoded statuses.

Run: cd /app/backend && python live_email_proof.py
"""
import asyncio
import sys

from motor.motor_asyncio import AsyncIOMotorClient

from app.config import settings
from app.repositories import store
from app.services import auth as auth_service
from app.util import iso, new_id

TARGET = "whymancreates.studio@gmail.com"


async def main() -> int:
    if not settings.RESEND_API_KEY:
        print("ABORT: RESEND_API_KEY is empty — nothing was sent.")
        return 2
    if not settings.RESEND_API_KEY.startswith("re_"):
        print(f"ABORT: RESEND_API_KEY does not look like a Resend key "
              f"(len={len(settings.RESEND_API_KEY)}, expected to start with 're_').")
        return 2

    print(f"from   : Dueo <{settings.RESEND_FROM}>")
    print(f"to     : {TARGET}")

    user = await store.get_user_by_email(TARGET)
    if not user:
        await store.insert_user({"id": new_id(), "email": TARGET,
                                 "full_name": "Resend Owner", "status": "active",
                                 "created_at": iso()})
        print("seeded : new active user for the target address")
    elif user.get("status") != "active":
        print(f"ABORT: user exists but status={user.get('status')!r}; request_code would skip the send.")
        return 2

    # Clear the per-email OTP rate counter so a re-run is not silently throttled.
    db = AsyncIOMotorClient(settings.MONGO_URL)[settings.DB_NAME]
    await db.rate_limits.delete_many({"key": {"$regex": TARGET}})

    result = await auth_service.request_code(TARGET, "127.0.0.1")
    print(f"api    : {result}")

    row = await db.emails_outbox.find_one({"to": TARGET}, sort=[("created_at", -1)])
    if not row:
        print("RESULT : NO OUTBOX ROW — request_code skipped the send (user/rate gate).")
        return 1
    print("outbox : status=%s provider=%s provider_id=%s" % (
        row.get("status"), row.get("provider"), row.get("provider_id")))
    if row.get("error"):
        print("error  : %s" % row["error"])
    print("verdict: %s" % ("DELIVERED TO RESEND (real message id above)"
                           if row.get("status") == "sent" else "NOT SENT — see error/status"))
    return 0 if row.get("status") == "sent" else 1


sys.exit(asyncio.run(main()))
