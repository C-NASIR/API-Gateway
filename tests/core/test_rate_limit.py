import pytest
import httpx
from httpx import ASGITransport
from asgi_lifespan import LifespanManager
from starlette.responses import JSONResponse
from app.core.gateway_router import GatewayRouter
from app.core.rate_limit import RateLimitMiddleware, InMemoryRateLimiter


# Fake backend handler
async def fake_backend(scope, receive, send):
    await JSONResponse({"status": "ok"})(scope, receive, send)


@pytest.mark.anyio
async def test_rate_limit_blocks_excessive_requests():
    backend_url = "http://fake-backend"
    route_table = { "/api": {"backend": backend_url}}

    # Backend stub
    transport = ASGITransport(app=fake_backend)
    fake_client = httpx.AsyncClient(transport=transport, base_url=backend_url)

    # Gateway with rate limit
    limiter = InMemoryRateLimiter(limit=3, window_seconds=1)
    app = RateLimitMiddleware(
        GatewayRouter(route_table=route_table, client=fake_client),
        limiter=limiter
    )

    async with LifespanManager(app):
        client = httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

        # First 3 requests should pass
        for i in range(3):
            res = await client.get("/api")
            assert res.status_code == 200
            assert res.headers["RateLimit-Limit"] == "3"
            assert res.headers["RateLimit-Remaining"] == str(2 - i)
            assert res.json() == {"status": "ok"}

        # 4th request should be blocked
        res = await client.get("/api")
        assert res.status_code == 429
        assert res.headers["RateLimit-Limit"] == "3"
        assert res.headers["RateLimit-Remaining"] == "0"
        assert "Retry-After" in res.headers
        assert "Too Many Requests" in res.text
