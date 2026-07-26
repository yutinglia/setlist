"""Shared bounded network behavior for every yt-dlp request."""

from __future__ import annotations


def bounded_network_options(
    *,
    socket_timeout: float,
    retries: int,
    extractor_retries: int,
) -> dict[str, float | int]:
    return {
        "socket_timeout": socket_timeout,
        "retries": retries,
        "extractor_retries": extractor_retries,
    }
