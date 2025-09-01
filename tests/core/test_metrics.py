import pytest
import httpx
from httpx import ASGITransport
from asgi_lifespan import LifespanManager
from starlette.responses import PlainTextResponse
from starlette.types import Scope, Receive, Send

from app.core.gateway_router import GatewayRouter
from app.core.admin_router import AdminRouter
from app.core.mount_admin_first import MountAdminFirst
from app.core.trace import TraceMiddleware
from app.core.rate_limiter import RateLimitMiddleware, InMemoryRateLimiter
from app.core.concurrency_limiter import ConcurrencyLimiterMiddleware
from app.core.path_router import PathRouter
from app.config.routes import ROUTE_TABLE

# Fake backend that always returns 200
async def fake_backend(scope: Scope, receive: Receive, send: Send):
    await PlainTextResponse("Hello from backend")(scope, receive, send)

@pytest.mark.anyio
async def test_metrics_endpoint_exposes_prometheus_data():
    backend_url = "http://backend1.local"
    route_table = {
        "/api": {"backend": backend_url},
    }

    # Setup the app as in main.py
    transport = ASGITransport(app=fake_backend)
    fake_client = httpx.AsyncClient(transport=transport, base_url=backend_url)

    path_router = PathRouter(route_table=route_table)
    gateway = GatewayRouter(path_router, client=fake_client)
    gateway = RateLimitMiddleware(gateway, InMemoryRateLimiter(limit=100, window_seconds=60))
    gateway = ConcurrencyLimiterMiddleware(gateway, max_concurrent=5)
    gateway = TraceMiddleware(gateway)

    admin = AdminRouter(gateway)
    app = MountAdminFirst(admin, gateway)

    async with LifespanManager(app):
        async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Trigger a few requests to generate metrics
            for _ in range(3):
                res = await client.get("/api")
                assert res.status_code == 200

            # Call the /__metrics endpoint
            res = await client.get("/__metrics")
            assert res.status_code == 200
            body = res.text

            # Check expected metric names
            assert "gateway_requests_total" in body
            assert "gateway_request_duration_seconds" in body
            assert "gateway_concurrent_requests" in body
            assert "gateway_rate_limited_requests_total" in body

            # Check expected route label is present
            assert 'route="/api"' in body
