"""Process-local fast view of the durable YouTube cooldown."""

from __future__ import annotations

import logging
import time

logger = logging.getLogger(__name__)


class YouTubeCooldown:
    """Injectable monotonic cooldown clock.

    PostgreSQL remains authoritative across processes; this object avoids a
    database read before every operation inside one process.
    """

    def __init__(self, default_seconds: float) -> None:
        self.default_seconds = default_seconds
        self._until: float | None = None

    def remaining(self) -> float:
        if self._until is None:
            return 0.0
        remaining = self._until - time.monotonic()
        if remaining <= 0:
            self._until = None
            return 0.0
        return remaining

    def activate(self, seconds: float | None = None) -> None:
        duration = self.default_seconds if seconds is None else seconds
        self._until = time.monotonic() + max(0.0, duration)
        logger.warning("YouTube cooldown set for %ss", duration)

    def clear(self) -> None:
        self._until = None
