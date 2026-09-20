"""Application configuration via pydantic-settings. Fails fast if a required var is missing."""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(ROOT_DIR / ".env"), extra="ignore")

    # Required — startup crashes if any of these are absent.
    MONGO_URL: str
    DB_NAME: str
    APP_URL: str
    SESSION_SECRET: str
    ENCRYPTION_KEY: str
    CRON_SECRET: str
    WEBHOOK_TEST_SECRET: str
    ADMIN_EMAILS: str

    # Optional / defaulted.
    WEBHOOK_CRON_SECRET: str = ""
    EMAIL_PROVIDER: str = "outbox"  # "resend" | "outbox"
    EMAIL_API_KEY: str = ""
    EMAIL_FROM: str = "no-reply@dueo.app"
    EMERGENT_EMAIL_KEY: str = ""
    EMAIL_FROM_NAME: str = "Dueo"
    EMAIL_REPLY_TO: str = ""
    EMERGENT_LLM_KEY: str = ""
    PILOT_COUNTRY: str = "IN"
    MAX_MEMBERS_PER_ORG: int = 1
    CORS_ORIGINS: str = ""

    @property
    def admin_emails(self) -> set[str]:
        return {e.strip().lower() for e in self.ADMIN_EMAILS.split(",") if e.strip()}

    @property
    def cors_origins(self) -> list[str]:
        raw = self.CORS_ORIGINS or self.APP_URL
        return [o.strip() for o in raw.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
