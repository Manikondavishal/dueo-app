"""Small pure helpers: ids, time, hashing, canonical json. No DB access here."""
import hashlib
import hmac
import json
import re
import secrets
import uuid
from datetime import datetime, timezone

from .config import settings

E164_IN = re.compile(r"^\+91[6-9]\d{9}$")
UDYAM_RE = re.compile(r"^UDYAM-[A-Z]{2}-\d{2}-\d{7}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def new_id() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime | None = None) -> str:
    return (dt or utcnow()).astimezone(timezone.utc).isoformat()


def norm_email(email: str) -> str:
    return (email or "").strip().casefold()


def valid_email(email: str) -> bool:
    return bool(EMAIL_RE.match(email or ""))


def hash_secret(value: str) -> str:
    """Keyed HMAC-SHA256 digest for OTP codes, session values and invite tokens."""
    return hmac.new(settings.SESSION_SECRET.encode(), value.encode(), hashlib.sha256).hexdigest()


def hash_ip(ip: str) -> str:
    return hashlib.sha256((settings.ENCRYPTION_KEY + (ip or "")).encode()).hexdigest()


def compare_digest(a: str, b: str) -> bool:
    return hmac.compare_digest(a or "", b or "")


def gen_token(n: int = 32) -> str:
    return secrets.token_urlsafe(n)


def gen_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def canonical_json(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()
