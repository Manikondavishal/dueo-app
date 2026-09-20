"""Append-only, hash-linked audit log with tamper detection."""
from pymongo.errors import DuplicateKeyError

from ..repositories import store
from ..util import canonical_json, iso, new_id, sha256_hex

GENESIS = "0" * 64

# Platform-level events share this chain; org events use the org_id as chain key.
PLATFORM_CHAIN = "platform"

EVENT_TYPES = {
    "lead_created",
    "lead_approved",
    "lead_held",
    "lead_rejected",
    "invite_used",
    "login_succeeded",
    "login_failed",
    "user_suspended",
    "org_created",
    "setup_completed",
}


def _compute_hash(prev_hash, chain_key, sequence, at, event_type, actor, payload) -> str:
    parts = [
        prev_hash,
        chain_key,
        str(sequence),
        at,
        event_type,
        actor or "",
        canonical_json(payload),
    ]
    return sha256_hex("|".join(parts))


async def append_event(event_type: str, actor: str | None, payload: dict, chain_key: str = PLATFORM_CHAIN) -> dict:
    """Append with optimistic concurrency; retry on a sequence collision."""
    for _ in range(6):
        head = await store.get_audit_head(chain_key)
        sequence = (head["sequence"] + 1) if head else 1
        prev_hash = head["hash"] if head else GENESIS
        at = iso()
        h = _compute_hash(prev_hash, chain_key, sequence, at, event_type, actor, payload)
        doc = {
            "id": new_id(),
            "chain_key": chain_key,
            "sequence": sequence,
            "prev_hash": prev_hash,
            "hash": h,
            "at": at,
            "event_type": event_type,
            "actor": actor,
            "payload": payload,
        }
        try:
            await store.append_audit_event(doc)
            return doc
        except DuplicateKeyError:
            continue
    raise RuntimeError("audit append failed after retries")


async def verify_audit_chain(chain_key: str = PLATFORM_CHAIN) -> dict:
    events = await store.list_audit_events(chain_key)
    prev = GENESIS
    for i, e in enumerate(events, start=1):
        if e["sequence"] != i:
            return {"valid": False, "reason": "sequence_gap", "at_sequence": e["sequence"]}
        if e["prev_hash"] != prev:
            return {"valid": False, "reason": "prev_hash_mismatch", "at_sequence": e["sequence"]}
        expected = _compute_hash(
            e["prev_hash"], chain_key, e["sequence"], e["at"], e["event_type"], e["actor"], e["payload"]
        )
        if expected != e["hash"]:
            return {"valid": False, "reason": "hash_mismatch", "at_sequence": e["sequence"]}
        prev = e["hash"]
    return {"valid": True, "count": len(events), "head": prev if events else None}
