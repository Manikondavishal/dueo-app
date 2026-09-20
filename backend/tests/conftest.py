"""Shared async test config.

Each async test gets a fresh Motor client bound to that test's own event loop,
injected into the store, so DB calls never hit a closed loop.
"""
import os

import pytest_asyncio
from motor.motor_asyncio import AsyncIOMotorClient

os.environ.setdefault("DB_NAME", "test_database")

from app.config import settings  # noqa: E402
from app.repositories import db as dbmod  # noqa: E402
from app.repositories import store  # noqa: E402


@pytest_asyncio.fixture(autouse=True)
async def _bind_db():
    client = AsyncIOMotorClient(settings.MONGO_URL)
    d = client[settings.DB_NAME]
    store.db = d
    dbmod.db = d
    yield d
    client.close()
