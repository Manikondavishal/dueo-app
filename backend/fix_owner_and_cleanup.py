"""One-off ops script (safe to re-run):

1. Make whymancreates.studio@gmail.com a fully working owner: attach it to the
   SAME organisation as the existing admin account if there is room, otherwise
   give it its own org. Without a membership `current_context` 403s
   `no_organization` and the dashboard is unreachable.
2. Delete only obvious test-suite leads (@example.com / @x.com / test-prefixed
   local parts). Real leads are never touched.

Run: cd /app/backend && python fix_owner_and_cleanup.py
"""
import asyncio
import re

from motor.motor_asyncio import AsyncIOMotorClient

from app.config import settings
from app.util import iso, new_id

TARGET = "whymancreates.studio@gmail.com"
PRIMARY = "vishalmanikonda@icloud.com"
TEST_EMAIL = re.compile(r"(@example\.com$|@x\.com$|^(test|rl_|known_|lock_|cancel_|susp_|inv_|newowner_|phase0)[^@]*@)", re.I)


async def main():
    db = AsyncIOMotorClient(settings.MONGO_URL)[settings.DB_NAME]

    # --- 1. owner account -----------------------------------------------
    # Repair the PRIMARY admin first: a historical unscoped
    # `organizations.delete_many({})` in a test fixture orphaned membership
    # rows, leaving real accounts at 404 `org_not_found`. Re-create any org
    # doc that a live membership still points at.
    for email, fallback_name in ((PRIMARY, "Alpha Traders"), (TARGET, "Whyman Creates")):
        u = await db.users.find_one({"email": email})
        if not u:
            continue
        mem = await db.organization_members.find_one({"user_id": u["id"]})
        if not mem:
            continue
        if not await db.organizations.find_one({"_id": mem["org_id"]}):
            await db.organizations.insert_one({
                "_id": mem["org_id"], "id": mem["org_id"],
                "display_name": fallback_name, "created_at": iso(),
            })
            print(f"org repair: recreated {mem['org_id']} for {email}")

    user = await db.users.find_one({"email": TARGET})
    if not user:
        user = {"_id": new_id(), "id": None, "email": TARGET, "full_name": "Whyman Creates",
                "status": "active", "created_at": iso()}
        user["id"] = user["_id"]
        await db.users.insert_one(user)
        print(f"user      : created {TARGET}")
    else:
        print(f"user      : exists {TARGET} (status={user.get('status')})")
    await db.users.update_one({"_id": user["id"]}, {"$set": {"status": "active"}})

    existing = await db.organization_members.find_one({"user_id": user["id"]})
    if existing:
        print(f"membership: already in org {existing['org_id']}")
        org_id = existing["org_id"]
    else:
        primary = await db.users.find_one({"email": PRIMARY})
        primary_mem = await db.organization_members.find_one({"user_id": (primary or {}).get("id")})
        org_id = None
        if primary_mem:
            seats = await db.organization_members.count_documents({"org_id": primary_mem["org_id"]})
            if seats < settings.MAX_MEMBERS_PER_ORG:
                org_id = primary_mem["org_id"]
                print(f"membership: joining existing org {org_id} ({seats} seat(s) used)")
            else:
                print(f"membership: primary org full ({seats}/{settings.MAX_MEMBERS_PER_ORG}) — creating own org")
        if not org_id:
            org_id = new_id()
            await db.organizations.insert_one({
                "_id": org_id, "id": org_id, "display_name": "Whyman Creates",
                "created_at": iso(),
            })
            print(f"org       : created {org_id}")
        mem_id = new_id()
        await db.organization_members.insert_one({
            "_id": mem_id, "id": mem_id, "org_id": org_id, "user_id": user["id"],
            "role": "owner", "status": "active", "created_at": iso(),
        })
        print(f"membership: created owner seat in {org_id}")

    org = await db.organizations.find_one({"_id": org_id})
    if not org:
        await db.organizations.insert_one({"_id": org_id, "id": org_id,
                                           "display_name": "Whyman Creates", "created_at": iso()})
        print(f"org       : repaired missing org doc {org_id}")

    # --- 2. lead cleanup -------------------------------------------------
    total = await db.waitlist_leads.count_documents({})
    kept, removed = [], 0
    for lead in await db.waitlist_leads.find().to_list(5000):
        addr = (lead.get("work_email") or "").strip()
        if addr and TEST_EMAIL.search(addr):
            await db.waitlist_leads.delete_one({"_id": lead["_id"]})
            removed += 1
        else:
            kept.append(addr or "(no email)")
    print(f"leads     : {total} before -> removed {removed} test rows, {len(kept)} kept")
    for addr in kept:
        print(f"            kept: {addr}")


asyncio.run(main())
