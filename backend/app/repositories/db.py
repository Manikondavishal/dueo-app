"""Motor client. Import site for the raw database handle (repositories only)."""
from motor.motor_asyncio import AsyncIOMotorClient

from ..config import settings

client = AsyncIOMotorClient(settings.MONGO_URL)
db = client[settings.DB_NAME]
