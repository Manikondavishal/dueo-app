"""Tenant isolation via TenantRepository: org_id is injected and client values ignored."""
import pytest

from app.repositories import store
from app.repositories.store import TenantRepository
from app.util import iso, new_id

COLL = "tenant_notes_test"


@pytest.mark.asyncio
async def test_tenant_repository_isolates_orgs():
    await store.db[COLL].delete_many({})
    org_a, org_b = new_id(), new_id()
    repo_a = TenantRepository(COLL, org_a)
    repo_b = TenantRepository(COLL, org_b)

    await repo_a.insert({"id": new_id(), "text": "a-secret", "created_at": iso()})
    await repo_b.insert({"id": new_id(), "text": "b-secret", "created_at": iso()})

    # Client tries to smuggle another org_id — it must be ignored.
    a_rows = await repo_a.find({"org_id": org_b})
    assert len(a_rows) == 1 and a_rows[0]["text"] == "a-secret"

    assert await repo_a.find_one({"text": "b-secret"}) is None
    res = await repo_a.delete_one({"text": "b-secret"})
    assert res.deleted_count == 0
    assert await repo_b.count() == 1
    await store.db[COLL].delete_many({})


@pytest.mark.asyncio
async def test_tenant_repository_requires_org():
    with pytest.raises(ValueError):
        TenantRepository(COLL, "")
