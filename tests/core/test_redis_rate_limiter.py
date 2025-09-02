import pytest
import httpx
import asyncio
from unittest import mock
import fakeredis
import redis.asyncio as redis
from unittest.mock import AsyncMock

from httpx import ASGITransport
from asgi_lifespan import LifespanManager
from starlette.responses import PlainTextResponse
from starlette.types import Scope, Receive, Send

from app.core.gateway_router import GatewayRouter
from app.core.redis_rate_limiter import RedisRateLimiter
from app.core.rate_limit_middleware import RateLimitMiddleware
from app.core.path_router import PathRouter


# Fake backend for testing
async def fake_backend(scope: Scope, receive: Receive, send: Send):
    await PlainTextResponse("OK")(scope, receive, send)


@pytest.mark.anyio
async def test_redis_rate_limiter_blocks_after_limit():

    backend_url = "http://fake-backend"
    route_table = { "/api": {"backend": backend_url}}

    # Backend stub
    transport = ASGITransport(app=fake_backend)
    fake_client = httpx.AsyncClient(transport=transport, base_url=backend_url)

    fake_transport = ASGITransport(app=fake_backend)
    fake_client = httpx.AsyncClient(transport=fake_transport, base_url=backend_url)

    # Patch the redis.evalsha method to simulate token bucket logic
    mock_redis = AsyncMock()
    # Simulate 3 successful tokens then reject
    responses = [0, 0, 0, 1]
    mock_redis.evalsha = AsyncMock(side_effect=responses)
    mock_redis.script_load = AsyncMock(return_value="mocked-sha")
    mock_redis.zcard = AsyncMock(return_value=3)

    # Gateway with rate limit
    limiter = RedisRateLimiter(mock_redis, limit=3, window_ms=10000)
    path_router = PathRouter(route_table=route_table)
    app = GatewayRouter(path_router, client=fake_client)
    app = RateLimitMiddleware(app, limiter)

    async with LifespanManager(app):
        transport = ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            # 3 allowed requests
            for _ in range(3):
                res = await client.get("/api")
                assert res.status_code == 200
                assert res.headers["ratelimit-limit"] == "3"
                assert "ratelimit-remaining" in res.headers

            # 4th should be rate limited
            res = await client.get("/api")
            assert res.status_code == 429
            assert res.text == "Too Many Requests"
            assert res.headers["ratelimit-limit"] == "3"
            assert res.headers["ratelimit-remaining"] == "0"
            assert "retry-after" in res.headers
