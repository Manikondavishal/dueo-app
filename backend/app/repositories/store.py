"""All MongoDB access lives here. Everything else calls these functions.

Collections: users, waitlist_leads, auth_otps, sessions, organizations,
organization_members, audit_events, audit_anchors, rate_limits, uploads,
webhook_events, scheduler_jobs, scheduler_runs, emails_outbox.
"""
from datetime import timedelta
from typing import Any, Optional

from pymongo import ASCENDING, DESCENDING, ReturnDocument

from ..util import iso, utcnow
from .db import db


# ----------------------------------------------------------------------------
# Tenant-scoped repository: injects org_id and ignores any client-supplied one.
# ----------------------------------------------------------------------------
class TenantRepository:
    def __init__(self, collection_name: str, org_id: str):
        if not org_id:
            raise ValueError("TenantRepository requires an org_id")
        self._c = db[collection_name]
        self._org = org_id

    def _scope(self, q: Optional[dict] = None) -> dict:
        q = dict(q or {})
        q.pop("org_id", None)  # never trust a client org_id
        q["org_id"] = self._org
        return q

    async def find(self, q: Optional[dict] = None, sort=None, limit: int = 500) -> list[dict]:
        cur = self._c.find(self._scope(q), {"_id": 0})
        if sort:
            cur = cur.sort(sort)
        return await cur.to_list(limit)

    async def find_one(self, q: Optional[dict] = None) -> Optional[dict]:
        return await self._c.find_one(self._scope(q), {"_id": 0})

    async def insert(self, doc: dict) -> dict:
        doc = {k: v for k, v in doc.items() if k != "org_id"}
        doc["org_id"] = self._org
        await self._c.insert_one(dict(doc))
        return {k: v for k, v in doc.items() if k != "_id"}

    async def update_one(self, q: dict, update: dict):
        return await self._c.update_one(self._scope(q), update)

    async def delete_one(self, q: dict):
        return await self._c.delete_one(self._scope(q))

    async def count(self, q: Optional[dict] = None) -> int:
        return await self._c.count_documents(self._scope(q))


def _clean(doc: Optional[dict]) -> Optional[dict]:
    if doc is None:
        return None
    doc.pop("_id", None)
    return doc


# ----------------------------------------------------------------------------
# Users
# ----------------------------------------------------------------------------
async def get_user_by_email(email: str) -> Optional[dict]:
    return _clean(await db.users.find_one({"email": email}))


async def get_user(user_id: str) -> Optional[dict]:
    return _clean(await db.users.find_one({"_id": user_id}))


async def insert_user(doc: dict) -> dict:
    await db.users.insert_one({**doc, "_id": doc["id"]})
    return _clean(dict(doc))


async def set_user_status(user_id: str, status: str):
    await db.users.update_one({"_id": user_id}, {"$set": {"status": status}})


async def list_users() -> list[dict]:
    return [_clean(d) for d in await db.users.find().sort("created_at", -1).to_list(500)]


# ----------------------------------------------------------------------------
# Waitlist leads
# ----------------------------------------------------------------------------
async def get_lead_by_email(email: str) -> Optional[dict]:
    return _clean(await db.waitlist_leads.find_one({"work_email": email}))


async def get_lead(lead_id: str) -> Optional[dict]:
    return _clean(await db.waitlist_leads.find_one({"_id": lead_id}))


async def insert_lead(doc: dict) -> dict:
    await db.waitlist_leads.insert_one({**doc, "_id": doc["id"]})
    return _clean(dict(doc))


async def update_lead(lead_id: str, fields: dict) -> Optional[dict]:
    return _clean(
        await db.waitlist_leads.find_one_and_update(
            {"_id": lead_id}, {"$set": fields}, return_document=ReturnDocument.AFTER
        )
    )


async def get_lead_by_invite_hash(token_hash: str) -> Optional[dict]:
    return _clean(await db.waitlist_leads.find_one({"invite_token_hash": token_hash}))


async def list_leads(status: Optional[str] = None) -> list[dict]:
    q = {"status": status} if status else {}
    return [_clean(d) for d in await db.waitlist_leads.find(q).sort("created_at", -1).to_list(500)]


async def list_leads_pending_reminder(cutoff_iso: str) -> list[dict]:
    q = {
        "status": "approved",
        "invite_reminder_sent": {"$ne": True},
        "invite_sent_at": {"$lte": cutoff_iso},
    }
    return [_clean(d) for d in await db.waitlist_leads.find(q).to_list(200)]


# ----------------------------------------------------------------------------
# OTP codes (TTL on expires_at)
# ----------------------------------------------------------------------------
async def deactivate_otps(email: str):
    await db.auth_otps.update_many({"email": email, "active": True}, {"$set": {"active": False}})


async def insert_otp(doc: dict):
    await db.auth_otps.insert_one({**doc, "_id": doc["id"]})


async def get_active_otp(email: str) -> Optional[dict]:
    return _clean(await db.auth_otps.find_one({"email": email, "active": True}))


async def bump_otp_attempts(otp_id: str, lock_until: Optional[Any] = None):
    update: dict = {"$inc": {"attempts": 1}}
    if lock_until is not None:
        update["$set"] = {"locked_until": lock_until}
    await db.auth_otps.update_one({"_id": otp_id}, update)


async def consume_otp(otp_id: str) -> Optional[dict]:
    return _clean(
        await db.auth_otps.find_one_and_update(
            {"_id": otp_id, "active": True, "expires_at": {"$gt": utcnow()}},
            {"$set": {"active": False, "consumed_at": iso()}},
            return_document=ReturnDocument.BEFORE,
        )
    )


# ----------------------------------------------------------------------------
# Sessions (TTL on expires_at)
# ----------------------------------------------------------------------------
async def insert_session(doc: dict):
    await db.sessions.insert_one({**doc, "_id": doc["id"]})


async def get_session_by_digest(digest: str) -> Optional[dict]:
    return _clean(await db.sessions.find_one({"digest": digest, "expires_at": {"$gt": utcnow()}}))


async def delete_session_by_digest(digest: str):
    await db.sessions.delete_one({"digest": digest})


async def delete_sessions_for_user(user_id: str):
    await db.sessions.delete_many({"user_id": user_id})


# ----------------------------------------------------------------------------
# Organizations + members
# ----------------------------------------------------------------------------
async def insert_org(doc: dict) -> dict:
    await db.organizations.insert_one({**doc, "_id": doc["id"]})
    return _clean(dict(doc))


async def get_org(org_id: str) -> Optional[dict]:
    return _clean(await db.organizations.find_one({"_id": org_id}))


async def update_org(org_id: str, fields: dict) -> Optional[dict]:
    return _clean(
        await db.organizations.find_one_and_update(
            {"_id": org_id}, {"$set": fields}, return_document=ReturnDocument.AFTER
        )
    )


async def insert_member(doc: dict):
    await db.organization_members.insert_one({**doc, "_id": doc["id"]})


async def count_members(org_id: str) -> int:
    return await db.organization_members.count_documents({"org_id": org_id})


async def get_membership_for_user(user_id: str) -> Optional[dict]:
    return _clean(await db.organization_members.find_one({"user_id": user_id, "status": "active"}))


# ----------------------------------------------------------------------------
# Audit chain (append-only) + anchors
# ----------------------------------------------------------------------------
async def get_audit_head(chain_key: str) -> Optional[dict]:
    doc = await db.audit_events.find_one({"chain_key": chain_key}, sort=[("sequence", -1)])
    return _clean(doc)


async def append_audit_event(doc: dict):
    """Insert relies on the unique index (chain_key, sequence) for optimistic concurrency."""
    await db.audit_events.insert_one({**doc, "_id": doc["id"]})


async def list_audit_events(chain_key: str) -> list[dict]:
    return [
        _clean(d)
        for d in await db.audit_events.find({"chain_key": chain_key}).sort("sequence", 1).to_list(5000)
    ]


async def all_chain_keys() -> list[str]:
    return await db.audit_events.distinct("chain_key")


async def insert_audit_anchor(doc: dict):
    await db.audit_anchors.insert_one({**doc, "_id": doc["id"]})


# ----------------------------------------------------------------------------
# Rate limits (TTL on expires_at)
# ----------------------------------------------------------------------------
async def rate_incr(kind: str, key: str, window_seconds: int) -> int:
    t = utcnow()
    doc = await db.rate_limits.find_one_and_update(
        {"kind": kind, "key": key, "expires_at": {"$gt": t}},
        {"$inc": {"count": 1}, "$setOnInsert": {"expires_at": t + timedelta(seconds=window_seconds)}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    return doc["count"]


# ----------------------------------------------------------------------------
# Uploads
# ----------------------------------------------------------------------------
async def insert_upload(doc: dict):
    await db.uploads.insert_one({**doc, "_id": doc["id"]})


async def get_upload(org_id: str, upload_id: str) -> Optional[dict]:
    return _clean(await db.uploads.find_one({"_id": upload_id, "org_id": org_id}))


# ----------------------------------------------------------------------------
# Webhook events (Phase 0)
# ----------------------------------------------------------------------------
async def insert_webhook_event(doc: dict):
    await db.webhook_events.insert_one({**doc, "_id": doc["id"]})


async def update_webhook_event(event_id: str, fields: dict):
    await db.webhook_events.update_one({"_id": event_id}, {"$set": fields})


async def count_webhook_events() -> int:
    return await db.webhook_events.count_documents({})


# ----------------------------------------------------------------------------
# Scheduler jobs (Phase 0 — atomic claim race)
# ----------------------------------------------------------------------------
async def enqueue_job(doc: dict):
    await db.scheduler_jobs.insert_one({**doc, "_id": doc["id"]})


async def claim_pending_job(worker_id: str) -> Optional[dict]:
    """Atomic claim: exactly one racing worker can flip pending -> running."""
    return _clean(
        await db.scheduler_jobs.find_one_and_update(
            {"status": "pending"},
            {"$set": {"status": "running", "worker_id": worker_id, "claimed_at": iso()}},
            sort=[("created_at", 1)],
            return_document=ReturnDocument.AFTER,
        )
    )


async def complete_job(job_id: str):
    await db.scheduler_jobs.update_one(
        {"_id": job_id}, {"$set": {"status": "done", "completed_at": iso()}}
    )


async def record_run(doc: dict):
    await db.scheduler_runs.insert_one({**doc, "_id": doc["id"]})


async def last_runs(limit: int = 10) -> list[dict]:
    return [_clean(d) for d in await db.scheduler_runs.find().sort("at", -1).to_list(limit)]


# ----------------------------------------------------------------------------
# Emails outbox
# ----------------------------------------------------------------------------
async def insert_outbox(doc: dict):
    await db.emails_outbox.insert_one({**doc, "_id": doc["id"]})


async def list_outbox(limit: int = 100) -> list[dict]:
    return [_clean(d) for d in await db.emails_outbox.find().sort("created_at", -1).to_list(limit)]


async def latest_login_email(email: str) -> Optional[dict]:
    return _clean(await db.emails_outbox.find_one({"to": email, "kind": "login_code"}, sort=[("created_at", -1)]))


# ----------------------------------------------------------------------------
# WhatsApp messages (Section-1 addition: payment_hub_id links a message to a
# real invoice; nullable so pre-hub development test rows still fit).
# ----------------------------------------------------------------------------
async def upsert_whatsapp_message(doc: dict):
    """Insert if the provider_sid is new; leave existing rows untouched. Used by
    the Twilio inbound webhook where retries may deliver the same MessageSid."""
    key = {"provider_sid": doc["provider_sid"]}
    await db.whatsapp_messages.update_one(key, {"$setOnInsert": {**doc, "_id": doc["id"]}}, upsert=True)


async def insert_whatsapp_message(doc: dict) -> dict:
    """Insert an outbound row we control (id and provider_sid provided)."""
    await db.whatsapp_messages.insert_one({**doc, "_id": doc["id"]})
    return _clean(dict(doc))


async def update_whatsapp_status(provider_sid: str, fields: dict):
    await db.whatsapp_messages.update_one({"provider_sid": provider_sid}, {"$set": fields})


async def get_whatsapp_message(provider_sid: str) -> Optional[dict]:
    return _clean(await db.whatsapp_messages.find_one({"provider_sid": provider_sid}))


async def list_whatsapp_for_hub(payment_hub_id: str, limit: int = 200) -> list[dict]:
    cur = db.whatsapp_messages.find({"payment_hub_id": payment_hub_id}).sort("created_at", 1)
    return [_clean(d) for d in await cur.to_list(limit)]


# ----------------------------------------------------------------------------
# Payment hubs + contacts + follow-up plans + follow-up messages (Section 1).
# The Section-1 brief lists 3 collections; a `payment_hubs` collection is added
# alongside because every listed collection references `payment_hub_id` and no
# hub-creation flow exists yet.
# ----------------------------------------------------------------------------
async def insert_payment_hub(doc: dict) -> dict:
    await db.payment_hubs.insert_one({**doc, "_id": doc["id"]})
    return _clean(dict(doc))


async def get_payment_hub(hub_id: str) -> Optional[dict]:
    return _clean(await db.payment_hubs.find_one({"_id": hub_id}))


async def get_payment_hub_by_token(token: str) -> Optional[dict]:
    return _clean(await db.payment_hubs.find_one({"public_token": token}))


async def list_payment_hubs_for_org(org_id: str, limit: int = 500) -> list[dict]:
    cur = db.payment_hubs.find({"org_id": org_id}).sort("created_at", -1)
    return [_clean(d) for d in await cur.to_list(limit)]


async def update_payment_hub(hub_id: str, fields: dict) -> Optional[dict]:
    await db.payment_hubs.update_one({"_id": hub_id}, {"$set": fields})
    return await get_payment_hub(hub_id)


async def insert_hub_contact(doc: dict) -> dict:
    await db.payment_hub_contacts.insert_one({**doc, "_id": doc["id"]})
    return _clean(dict(doc))


async def list_hub_contacts(payment_hub_id: str) -> list[dict]:
    cur = db.payment_hub_contacts.find({"payment_hub_id": payment_hub_id}).sort("created_at", 1)
    return [_clean(d) for d in await cur.to_list(20)]


async def replace_hub_contacts(payment_hub_id: str, contacts: list[dict]) -> list[dict]:
    """Section-3 semantics: contacts are edited as a set. Wipe existing rows
    for the hub, insert the new ones in one shot, return them."""
    await db.payment_hub_contacts.delete_many({"payment_hub_id": payment_hub_id})
    if contacts:
        docs = [{**c, "_id": c["id"]} for c in contacts]
        await db.payment_hub_contacts.insert_many(docs)
    return await list_hub_contacts(payment_hub_id)


async def insert_follow_up_plan(doc: dict) -> dict:
    await db.follow_up_plans.insert_one({**doc, "_id": doc["id"]})
    return _clean(dict(doc))


async def get_follow_up_plan(payment_hub_id: str) -> Optional[dict]:
    return _clean(await db.follow_up_plans.find_one({"payment_hub_id": payment_hub_id}, sort=[("created_at", -1)]))


async def update_follow_up_plan(plan_id: str, fields: dict):
    await db.follow_up_plans.update_one({"_id": plan_id}, {"$set": fields})


async def insert_follow_up_message(doc: dict) -> dict:
    await db.follow_up_messages.insert_one({**doc, "_id": doc["id"]})
    return _clean(dict(doc))


async def update_follow_up_message(msg_id: str, fields: dict):
    await db.follow_up_messages.update_one({"_id": msg_id}, {"$set": fields})


async def list_follow_up_messages_for_hub(payment_hub_id: str) -> list[dict]:
    cur = db.follow_up_messages.find({"payment_hub_id": payment_hub_id}).sort("scheduled_for", 1)
    return [_clean(d) for d in await cur.to_list(500)]


async def next_scheduled_follow_ups(cutoff_iso: str, limit: int = 100) -> list[dict]:
    cur = (
        db.follow_up_messages.find({"status": "scheduled", "scheduled_for": {"$lte": cutoff_iso}})
        .sort("scheduled_for", 1)
    )
    return [_clean(d) for d in await cur.to_list(limit)]


# ----------------------------------------------------------------------------
# Indexes + migration tracking (kept here so only repositories touch the DB)
# ----------------------------------------------------------------------------
async def ensure_indexes():
    await db.users.create_index("email", unique=True)
    await db.waitlist_leads.create_index("work_email", unique=True)
    await db.waitlist_leads.create_index("invite_token_hash", sparse=True)
    await db.auth_otps.create_index("expires_at", expireAfterSeconds=0)
    await db.auth_otps.create_index([("email", ASCENDING), ("active", ASCENDING)])
    await db.sessions.create_index("expires_at", expireAfterSeconds=0)
    await db.sessions.create_index("digest")
    await db.sessions.create_index("user_id")
    await db.organization_members.create_index(
        [("org_id", ASCENDING), ("user_id", ASCENDING)], unique=True
    )
    await db.audit_events.create_index(
        [("chain_key", ASCENDING), ("sequence", ASCENDING)], unique=True
    )
    await db.audit_events.create_index([("chain_key", ASCENDING), ("sequence", DESCENDING)])
    await db.rate_limits.create_index("expires_at", expireAfterSeconds=0)
    await db.rate_limits.create_index([("kind", ASCENDING), ("key", ASCENDING)])
    await db.uploads.create_index("org_id")
    await db.scheduler_jobs.create_index("status")
    await db.webhook_events.create_index("created_at")


async def ensure_indexes_v2():
    """Section-1 collections: whatsapp_messages, payment_hubs, payment_hub_contacts,
    follow_up_plans, follow_up_messages."""
    await db.whatsapp_messages.create_index("provider_sid", unique=True)
    await db.whatsapp_messages.create_index("payment_hub_id")
    await db.whatsapp_messages.create_index([("org_id", ASCENDING), ("created_at", DESCENDING)])
    await db.payment_hubs.create_index("org_id")
    await db.payment_hubs.create_index("public_token", unique=True, sparse=True)
    await db.payment_hub_contacts.create_index([("payment_hub_id", ASCENDING), ("role", ASCENDING)])
    await db.follow_up_plans.create_index([("payment_hub_id", ASCENDING), ("created_at", DESCENDING)])
    await db.follow_up_messages.create_index("payment_hub_id")
    await db.follow_up_messages.create_index([("status", ASCENDING), ("scheduled_for", ASCENDING)])


async def applied_migrations() -> set[str]:
    return set(await db.migrations.distinct("name"))


async def record_migration(name: str):
    await db.migrations.update_one({"name": name}, {"$set": {"name": name}}, upsert=True)
