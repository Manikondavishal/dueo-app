"""LLMProvider wrapper around the Emergent LLM key (Gemini 3 Flash, vision)."""
import base64
import json
import logging
import re

from emergentintegrations.llm.chat import (
    ImageContent,
    LlmChat,
    StreamDone,
    TextDelta,
    UserMessage,
)

from ..config import settings
from ..util import new_id

logger = logging.getLogger("dueo.llm")

_JSON_BLOCK = re.compile(r"\{.*\}", re.S)


class LLMProvider:
    def __init__(self, model: str = "gemini-3-flash-preview", provider: str = "gemini"):
        self.model = model
        self.provider = provider

    def _chat(self, system_message: str) -> LlmChat:
        return LlmChat(
            api_key=settings.EMERGENT_LLM_KEY,
            session_id=new_id(),
            system_message=system_message,
        ).with_model(self.provider, self.model)

    async def _collect(self, chat: LlmChat, message: UserMessage) -> str:
        out = []
        async for ev in chat.stream_message(message):
            if isinstance(ev, TextDelta):
                out.append(ev.content)
            elif isinstance(ev, StreamDone):
                break
        return "".join(out)

    async def extract_json_from_image(self, image_base64: str, instruction: str) -> dict:
        """Send an image + instruction and parse a structured JSON object out of the reply."""
        system = (
            "You extract structured data and return ONLY a single minified JSON object. "
            "No prose, no markdown fences."
        )
        chat = self._chat(system)
        message = UserMessage(text=instruction, file_contents=[ImageContent(image_base64=image_base64)])
        raw = await self._collect(chat, message)
        return self._parse_json(raw)

    @staticmethod
    def _parse_json(raw: str) -> dict:
        text = (raw or "").strip()
        if text.startswith("```"):
            text = text.strip("`")
            text = text[4:] if text.lower().startswith("json") else text
        try:
            return json.loads(text)
        except Exception:  # noqa: BLE001
            m = _JSON_BLOCK.search(text)
            if m:
                return json.loads(m.group(0))
            raise


llm_provider = LLMProvider()


def sample_invoice_image_b64() -> str:
    """Tiny generated PNG with invoice-like text for the Phase 0 self-test."""
    # 1x1 transparent PNG is rejected by the vision model guardrails; the Phase 0
    # test supplies a real rendered image instead. This helper is a placeholder.
    return base64.b64encode(b"").decode()
