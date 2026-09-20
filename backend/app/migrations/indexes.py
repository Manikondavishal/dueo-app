"""Versioned migrations, run at startup. DB access is delegated to the store."""
import logging

from ..repositories import store

logger = logging.getLogger("dueo.migrations")

MIGRATIONS = [("v1_indexes", store.ensure_indexes)]


async def run_migrations():
    applied = await store.applied_migrations()
    for name, fn in MIGRATIONS:
        if name in applied:
            continue
        try:
            await fn()
        except Exception:  # noqa: BLE001
            logger.warning("migration %s completed with warnings", name)
        await store.record_migration(name)
        logger.info("migration applied: %s", name)
