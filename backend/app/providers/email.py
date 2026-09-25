"""Email provider. Sends directly through Resend using OUR OWN `RESEND_API_KEY`
(the Emergent-managed `EMERGENT_EMAIL_KEY` pipe is retired), and always records
a copy in the emails_outbox collection so every flow is testable and nothing
sensitive is lost. Plain transactional emails only (no marketing)."""
import ipaddress
import logging
import re
from html import escape
from html.parser import HTMLParser
from urllib.parse import urlparse

import httpx

from ..config import settings
from ..repositories import store
from ..util import iso, new_id

logger = logging.getLogger("dueo.email")

RESEND_SEND_URL = "https://api.resend.com/emails"
# Resend rejects direct HTTP calls without a User-Agent (403).
RESEND_USER_AGENT = "dueo-api/1.0"

_SHORTENERS = ("bit.ly", "tinyurl.com", "t.co", "is.gd", "cutt.ly", "goo.gl", "rebrand.ly")
_HOSTISH = re.compile(r"\b(?:https?://)?((?:[a-z0-9-]+\.)+[a-z]{2,})", re.I)


def _host_ok(host: str) -> bool:
    if not host or "xn--" in host:
        return False
    try:
        ipaddress.ip_address(host)
        return False
    except ValueError:
        pass
    return not any(host == s or host.endswith("." + s) for s in _SHORTENERS)


def _same_site(shown: str, real: str) -> bool:
    return shown == real or real.endswith("." + shown) or shown.endswith("." + real)


class _EmailScan(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags, self.urls, self.anchors = set(), [], []
        self._href, self._text = None, []

    def handle_starttag(self, tag, attrs):
        self.tags.add(tag.lower())
        self.urls += [v for k, v in attrs if k.lower() in ("href", "src") and v]
        if tag.lower() == "a":
            self._href = dict((k.lower(), v) for k, v in attrs).get("href")
            self._text = []

    def handle_data(self, data):
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag.lower() == "a" and self._href is not None:
            self.anchors.append((self._href, "".join(self._text)))
            self._href, self._text = None, []


def _assert_safe_email(subject: str, html: str) -> None:
    scan = _EmailScan()
    scan.feed(html)
    if scan.tags & {"form", "input", "textarea", "select"}:
        raise ValueError("No forms or input fields in email")
    for url in scan.urls:
        low = url.strip().lower()
        if low.startswith(("mailto:", "tel:", "cid:", "#")):
            continue
        if not low.startswith("https://"):
            raise ValueError(f"Email links/assets must be absolute https: {url!r}")
        host = urlparse(low).hostname or ""
        if not _host_ok(host) or urlparse(low).username is not None:
            raise ValueError(f"Unsafe URL: {url!r}")
    for href, text in scan.anchors:
        real = urlparse(href.strip().lower()).hostname or ""
        if not real:
            continue
        for m in _HOSTISH.finditer(text):
            if not _same_site(m.group(1).lower(), real):
                raise ValueError(f"Anchor text {m.group(1)!r} != link host {real!r}")


def _sender() -> str:
    """Resend wants an RFC-5322 `From`. Display name + the configured address."""
    name = (settings.EMAIL_FROM_NAME or "").strip()
    addr = settings.RESEND_FROM
    return f"{name} <{addr}>" if name else addr


async def _resend_send(to: str, subject: str, html: str) -> str | None:
    payload: dict = {
        "from": _sender(),
        "to": [to],
        "subject": subject,
        "html": html,
    }
    if settings.EMAIL_REPLY_TO:
        payload["reply_to"] = settings.EMAIL_REPLY_TO
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            RESEND_SEND_URL,
            headers={
                "Authorization": f"Bearer {settings.RESEND_API_KEY}",
                "Content-Type": "application/json",
                "User-Agent": RESEND_USER_AGENT,
            },
            json=payload,
        )
    if resp.status_code >= 400:
        # Body carries Resend's error name/message (never the key) — keep it so
        # a 403 "resend.dev can only mail the account owner" is diagnosable.
        raise RuntimeError(f"resend {resp.status_code}: {resp.text[:300]}")
    return resp.json().get("id")


async def send_email(*, to: str, subject: str, html: str, kind: str = "generic") -> dict:
    """Send an email (server-side templates only). Always logs to the outbox."""
    _assert_safe_email(subject, html)
    provider = settings.EMAIL_PROVIDER
    status, provider_id, error = "queued", None, None
    if provider == "resend" and settings.RESEND_API_KEY:
        try:
            provider_id = await _resend_send(to, subject, html)
            status = "sent"
        except Exception as e:  # noqa: BLE001
            status, error = "failed", str(e)[:300]
            logger.error("email send failed kind=%s status=failed", kind)
    else:
        status = "outbox"
    await store.insert_outbox(
        {
            "id": new_id(),
            "to": to,
            "subject": subject,
            "html": html,
            "kind": kind,
            "provider": provider,
            "status": status,
            "provider_id": provider_id,
            "error": error,
            "created_at": iso(),
        }
    )
    return {"status": status, "provider_id": provider_id}
