"""WhatsApp provider abstraction. Every outbound WhatsApp message goes through
this interface so we can swap providers (Twilio -> Gupshup / WATI / Meta Cloud)
later without touching business logic. The current concrete implementation talks
to Twilio's REST API using the async HTTP client from `twilio` v9."""
import logging
from dataclasses import dataclass
from typing import Optional, Protocol

from twilio.http.async_http_client import AsyncTwilioHttpClient
from twilio.rest import Client

from ..config import settings

logger = logging.getLogger("dueo.whatsapp")


@dataclass
class SentMessage:
    provider_id: str
    status: str


def _wa_addr(to: str) -> str:
    """Normalise an E.164 phone to a `whatsapp:` address if not already prefixed."""
    to = (to or "").strip()
    return to if to.startswith("whatsapp:") else f"whatsapp:{to}"


class WhatsAppProvider(Protocol):
    async def send_freeform(
        self,
        to: str,
        body: str,
        status_callback: Optional[str] = None,
    ) -> SentMessage: ...


class TwilioWhatsAppProvider:
    """Real Twilio implementation. Lazily builds a client so importing this
    module does not require valid creds (tests can import + stub freely)."""

    def __init__(self) -> None:
        self._client: Optional[Client] = None

    def _c(self) -> Client:
        if self._client is None:
            self._client = Client(
                settings.TWILIO_ACCOUNT_SID,
                settings.TWILIO_AUTH_TOKEN,
                http_client=AsyncTwilioHttpClient(),
            )
        return self._client

    async def send_freeform(self, to, body, status_callback=None):
        kwargs = {
            "from_": settings.ORG_WHATSAPP_FROM,
            "to": _wa_addr(to),
            "body": body,
        }
        if status_callback:
            kwargs["status_callback"] = status_callback
        msg = await self._c().messages.create_async(**kwargs)
        return SentMessage(provider_id=msg.sid, status=msg.status)


class LogOnlyWhatsAppProvider:
    """No-op provider used when Twilio creds are missing. Records a log line;
    the caller still persists the outbound `whatsapp_messages` row so the UI
    stays coherent even without a live provider."""

    async def send_freeform(self, to, body, status_callback=None):
        logger.warning("whatsapp send stubbed (no twilio creds) to=%s chars=%d", to, len(body or ""))
        return SentMessage(provider_id=f"stub_{_wa_addr(to)}", status="queued")


def get_provider() -> WhatsAppProvider:
    if settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN and settings.ORG_WHATSAPP_FROM:
        return TwilioWhatsAppProvider()
    return LogOnlyWhatsAppProvider()


# Module-level singleton, cheap to import.
provider: WhatsAppProvider = get_provider()
