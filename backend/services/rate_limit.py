"""In-process anonymous API rate limiting with trusted-proxy awareness."""

from __future__ import annotations

import asyncio
import math
import time
from dataclasses import dataclass
from ipaddress import IPv4Address, IPv6Address, ip_address

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse, Response

import config
from services.auth import SESSION_COOKIE_NAME, decode_admin_session
from utils.http_cache import prevent_private_response_caching

IPAddress = IPv4Address | IPv6Address


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    limit: int
    remaining: int
    reset_after_seconds: int


@dataclass
class _Window:
    count: int
    resets_at: float


class FixedWindowRateLimiter:
    def __init__(self, limit: int, window_seconds: int):
        self.limit = limit
        self.window_seconds = window_seconds
        self._windows: dict[str, _Window] = {}
        self._lock = asyncio.Lock()

    async def check(
        self,
        key: str,
        *,
        now: float | None = None,
    ) -> RateLimitDecision:
        current = time.monotonic() if now is None else now
        async with self._lock:
            window = self._windows.get(key)
            if window is None or window.resets_at <= current:
                window = _Window(count=0, resets_at=current + self.window_seconds)
                self._windows[key] = window

            allowed = window.count < self.limit
            if allowed:
                window.count += 1
            remaining = max(0, self.limit - window.count)
            reset_after = max(1, math.ceil(window.resets_at - current))

            if len(self._windows) > 10_000:
                self._windows = {
                    stored_key: stored
                    for stored_key, stored in self._windows.items()
                    if stored.resets_at > current
                }

        return RateLimitDecision(
            allowed=allowed,
            limit=self.limit,
            remaining=remaining,
            reset_after_seconds=reset_after,
        )


class GuestRateLimitMiddleware(BaseHTTPMiddleware):
    """Limit unauthenticated `/v1` traffic; admin sessions are exempt."""

    def __init__(self, app):
        super().__init__(app)
        self.guest_limiter = FixedWindowRateLimiter(
            config.GUEST_RATE_LIMIT_REQUESTS,
            config.GUEST_RATE_LIMIT_WINDOW_SECONDS,
        )
        self.login_limiter = FixedWindowRateLimiter(
            config.LOGIN_RATE_LIMIT_REQUESTS,
            config.LOGIN_RATE_LIMIT_WINDOW_SECONDS,
        )

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        admin = decode_admin_session(request.cookies.get(SESSION_COOKIE_NAME))
        if (
            request.url.path.startswith("/v1")
            and request.method != "OPTIONS"
            and admin is not None
        ):
            response = await call_next(request)
            prevent_private_response_caching(response)
            return response

        if (
            not config.GUEST_RATE_LIMIT_ENABLED
            or request.method == "OPTIONS"
            or not request.url.path.startswith("/v1")
        ):
            return await call_next(request)

        client_key = resolve_client_ip(request)
        limiter = (
            self.login_limiter
            if request.url.path == "/v1/auth/login"
            else self.guest_limiter
        )
        decision = await limiter.check(client_key)
        headers = _rate_limit_headers(decision)
        if not decision.allowed:
            headers["Retry-After"] = str(decision.reset_after_seconds)
            headers["Cache-Control"] = "private, no-store"
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests; try again later"},
                headers=headers,
            )

        response = await call_next(request)
        response.headers.update(headers)
        if request.url.path.startswith("/v1/auth/"):
            prevent_private_response_caching(response)
        return response


def resolve_client_ip(request: Request) -> str:
    peer = request.client.host if request.client else "unknown"
    try:
        peer_ip = ip_address(peer)
    except ValueError:
        return peer

    if not _is_trusted_proxy(peer_ip):
        return str(peer_ip)

    forwarded = request.headers.get("x-forwarded-for", "")
    chain: list[IPAddress] = []
    for raw in forwarded.split(","):
        try:
            chain.append(ip_address(raw.strip()))
        except ValueError:
            continue
    chain.append(peer_ip)

    for candidate in reversed(chain):
        if not _is_trusted_proxy(candidate):
            return str(candidate)
    return str(chain[0]) if chain else str(peer_ip)


def _is_trusted_proxy(address: IPAddress) -> bool:
    return any(address in network for network in config.TRUSTED_PROXY_CIDRS)


def _rate_limit_headers(decision: RateLimitDecision) -> dict[str, str]:
    values = {
        "RateLimit-Limit": str(decision.limit),
        "RateLimit-Remaining": str(decision.remaining),
        "RateLimit-Reset": str(decision.reset_after_seconds),
    }
    return values | {f"X-{name}": value for name, value in values.items()}
