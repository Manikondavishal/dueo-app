"""Audit chain: append-only, hash-linked, and tamper-detectable."""
import pytest
from pymongo.errors import DuplicateKeyError

from app.repositories import store
from app.services import audit
from app.util import new_id


@pytest.mark.asyncio
async def test_audit_chain_valid_and_tamper_detected():
    chain = "test_chain_" + new_id()
    await store.db.audit_events.delete_many({"chain_key": chain})

    await audit.append_event("lead_created", "a@x.com", {"lead_id": "1"}, chain_key=chain)
    await audit.append_event("lead_approved", "admin@x.com", {"lead_id": "1"}, chain_key=chain)
    await audit.append_event("invite_used", "a@x.com", {"org_id": "o1"}, chain_key=chain)

    result = await audit.verify_audit_chain(chain)
    assert result["valid"] is True and result["count"] == 3

    await store.db.audit_events.update_one(
        {"chain_key": chain, "sequence": 2}, {"$set": {"payload": {"lead_id": "HACKED"}}}
    )
    tampered = await audit.verify_audit_chain(chain)
    assert tampered["valid"] is False and tampered["at_sequence"] == 2
    await store.db.audit_events.delete_many({"chain_key": chain})


@pytest.mark.asyncio
async def test_audit_sequence_unique_index():
    chain = "seqtest_" + new_id()
    doc = {"id": new_id(), "chain_key": chain, "sequence": 1, "prev_hash": "x", "hash": "h",
           "at": "t", "event_type": "e", "actor": None, "payload": {}}
    await store.db.audit_events.insert_one({**doc, "_id": doc["id"]})
    with pytest.raises(DuplicateKeyError):
        dupe = {**doc, "id": new_id()}
        await store.db.audit_events.insert_one({**dupe, "_id": dupe["id"]})
    await store.db.audit_events.delete_many({"chain_key": chain})
