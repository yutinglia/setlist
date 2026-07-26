"""Optional LLM cleaning of setlist comments (skipped unless enabled via env)."""

from __future__ import annotations

import logging

import httpx

from config import (
    LLM_API_KEY,
    LLM_API_URL,
    LLM_CLEANING_ENABLED,
    LLM_MAX_INPUT_CHARS,
    LLM_MODEL,
    LLM_TIMEOUT_SECONDS,
)

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You clean VTuber karaoke setlist comments. "
    "Reply with ONLY the cleaned setlist: one song per line as "
    "`TIMESTAMP TITLE` where TIMESTAMP is mm:ss or hh:mm:ss. "
    "Keep original titles; strip chatter, numbering noise, and duplicate lines. "
    "Do not invent songs that are not in the input."
)


async def maybe_clean_song_list_comment(text: str) -> str | None:
    """Normalize a setlist comment via an OpenAI-compatible chat API.

    Returns cleaned text, or ``None`` when cleaning is disabled, misconfigured,
    or the request fails (caller should keep the regex extract).
    """
    if not LLM_CLEANING_ENABLED:
        return None

    if not LLM_API_KEY:
        logger.warning(
            "LLM_CLEANING_ENABLED is set but LLM_API_KEY is empty; skipping clean"
        )
        return None

    raw = (text or "").strip()
    if not raw:
        return None
    if len(raw) > LLM_MAX_INPUT_CHARS:
        logger.warning(
            "Setlist comment exceeds LLM_MAX_INPUT_CHARS=%s; truncating",
            LLM_MAX_INPUT_CHARS,
        )
        raw = raw[:LLM_MAX_INPUT_CHARS]

    payload = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": raw},
        ],
        "temperature": 0,
    }
    headers = {
        "Authorization": f"Bearer {LLM_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=LLM_TIMEOUT_SECONDS) as client:
            response = await client.post(LLM_API_URL, json=payload, headers=headers)
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

    logger.info("LLM cleaned setlist comment (%s → %s chars)", len(raw), len(cleaned))
    return cleaned
