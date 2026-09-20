"""Entry point loaded by supervisor: `uvicorn server:app`."""
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

from app.main import app  # noqa: E402

__all__ = ["app"]
