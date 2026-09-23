"""FastAPI composition root."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from .config import settings
from .jobs import scheduler
from .migrations.indexes import run_migrations
from .routers import admin, appspace, auth, cron, dashboard, dev, hubs, public, public_hub, uploads, webhooks, whatsapp
from .security import SecurityMiddleware

logging.basicConfig(
    level=logging.INFO,
    format='{"ts":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","msg":"%(message)s"}',
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await run_migrations()
    try:
        from .providers import storage

        storage.init_storage()
    except Exception:  # noqa: BLE001
        logging.getLogger("dueo").warning("object storage init deferred")
    scheduler.start_scheduler()
    yield
    scheduler.stop_scheduler()


app = FastAPI(title="Dueo", lifespan=lifespan)

app.add_middleware(SecurityMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=r"https://.*\.(emergentagent\.com|emergentcf\.cloud)",
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["*"],
)

for r in (public, auth, appspace, admin, uploads, webhooks, cron, dev, whatsapp, hubs, public_hub, dashboard):
    app.include_router(r.router)
