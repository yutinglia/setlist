"""Anonymous fixed-window rate limiting and proxy address handling."""

from ipaddress import ip_network

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request

import config
from services import auth
from services.auth import SESSION_COOKIE_NAME
from services.rate_limit import (
    FixedWindowRateLimiter,
    GuestRateLimitMiddleware,
    resolve_client_ip,
)


@pytest.mark.asyncio
async def test_fixed_window_limiter_blocks_and_resets():
    limiter = FixedWindowRateLimiter(limit=2, window_seconds=60)

    first = await limiter.check("client", now=100)
    second = await limiter.check("client", now=101)
    blocked = await limiter.check("client", now=102)
    reset = await limiter.check("client", now=161)

    assert first.allowed is True
    assert first.remaining == 1
    assert second.allowed is True
    assert second.remaining == 0
    assert blocked.allowed is False
    assert blocked.reset_after_seconds == 58
    assert reset.allowed is True
    assert reset.remaining == 1


def test_forwarded_address_is_ignored_from_untrusted_peer(monkeypatch):
    monkeypatch.setattr(config, "TRUSTED_PROXY_CIDRS", ())
    request = _request("203.0.113.5", "198.51.100.20")

    assert resolve_client_ip(request) == "203.0.113.5"


def test_forwarded_chain_is_used_only_behind_trusted_proxy(monkeypatch):
    monkeypatch.setattr(
        config,
        "TRUSTED_PROXY_CIDRS",
        (ip_network("10.0.0.0/8"),),
    )
    request = _request("10.0.0.8", "198.51.100.20, 10.0.0.7")

    assert resolve_client_ip(request) == "198.51.100.20"


def test_guest_api_limit_headers_and_admin_exemption(monkeypatch):
    monkeypatch.setattr(config, "GUEST_RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(config, "GUEST_RATE_LIMIT_REQUESTS", 2)
    monkeypatch.setattr(config, "GUEST_RATE_LIMIT_WINDOW_SECONDS", 60)
    monkeypatch.setattr(config, "LOGIN_RATE_LIMIT_REQUESTS", 5)
    monkeypatch.setattr(config, "LOGIN_RATE_LIMIT_WINDOW_SECONDS", 300)
    monkeypatch.setattr(config, "TRUSTED_PROXY_CIDRS", ())
    monkeypatch.setattr(config, "ADMIN_USERNAME", "operator")
    monkeypatch.setattr(
        config,
        "ADMIN_PASSWORD_HASH",
        auth._password_hasher.hash("a-strong-test-password"),
    )
    monkeypatch.setattr(config, "SESSION_SECRET", "s" * 48)
    monkeypatch.setattr(config, "AUTH_SESSION_TTL_SECONDS", 3600)

    app = FastAPI()
    app.add_middleware(GuestRateLimitMiddleware)

    @app.get("/v1/ping")
    async def ping():
        return {"ok": True}

    with TestClient(app) as client:
        first = client.get("/v1/ping")
        second = client.get("/v1/ping")
        blocked = client.get("/v1/ping")

        assert first.status_code == 200
        assert first.headers["ratelimit-limit"] == "2"
        assert second.headers["ratelimit-remaining"] == "0"
        assert blocked.status_code == 429
        assert blocked.headers["retry-after"]

        token, _ = auth.create_admin_session()
        client.cookies.set(SESSION_COOKIE_NAME, token, path="/v1")
        assert client.get("/v1/ping").status_code == 200


def _request(peer: str, forwarded_for: str) -> Request:
    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": "/v1/health",
            "raw_path": b"/v1/health",
            "query_string": b"",
            "headers": [
                (b"x-forwarded-for", forwarded_for.encode("ascii")),
            ],
            "client": (peer, 12345),
            "server": ("testserver", 80),
        }
    )
