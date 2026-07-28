"""Optional LLM cleaning of setlist comments (skipped unless enabled via env)."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any, Protocol

import httpx2

import config
from config import LlmSettings

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You clean VTuber karaoke setlist comments. "
    "Reply with ONLY the cleaned setlist: one song per line as "
    "`TIMESTAMP TITLE` where TIMESTAMP is mm:ss or hh:mm:ss. "
    "Keep original titles; strip chatter, numbering noise, and duplicate lines. "
    "Do not invent songs that are not in the input."
)


class SongListCleaner(Protocol):
    async def clean(self, text: str) -> str | None: ...


class LlmSongListCleaner:
    """OpenAI-compatible cleaner with injected settings and HTTP client."""

    def __init__(
        self,
        settings: LlmSettings,
        *,
        client_factory: Callable[..., Any] = httpx2.AsyncClient,
    ) -> None:
        self.settings = settings
        self.client_factory = client_factory

    async def clean(self, text: str) -> str | None:
        """Normalize a setlist comment, retaining regex output on failure."""
        if not self.settings.enabled:
            return None

        if not self.settings.api_key:
            logger.warning(
                "LLM_CLEANING_ENABLED is set but LLM_API_KEY is empty; skipping clean"
            )
            return None

        raw = (text or "").strip()
        if not raw:
            return None
        if len(raw) > self.settings.max_input_chars:
            logger.warning(
                "Setlist comment exceeds LLM_MAX_INPUT_CHARS=%s; truncating",
                self.settings.max_input_chars,
            )
            raw = raw[: self.settings.max_input_chars]

        payload = {
            "model": self.settings.model,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": raw},
            ],
            "temperature": 0,
        }
        headers = {
            "Authorization": f"Bearer {self.settings.api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with self.client_factory(
                timeout=self.settings.timeout_seconds
            ) as client:
                response = await client.post(
                    self.settings.api_url,
                    json=payload,
                    headers=headers,
                )
                response.raise_for_status()
                data = response.json()
        except Exception:
            logger.exception("LLM setlist cleaning request failed")
            return None

        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            logger.warning("Unexpected LLM response shape: %s", type(data).__name__)
            return None

        if not isinstance(content, str):
            return None

        cleaned = content.strip()
        if not cleaned:
            logger.warning("LLM returned empty setlist text")
            return None

        logger.info(
            "LLM cleaned setlist comment (%s → %s chars)",
            len(raw),
            len(cleaned),
        )
        return cleaned


async def maybe_clean_song_list_comment(text: str) -> str | None:
    """Compatibility wrapper for direct callers."""

    return await LlmSongListCleaner(config.get_settings().llm).clean(text)
