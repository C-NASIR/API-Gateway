import pytest
import httpx
import asyncio
from httpx import ASGITransport
from asgi_lifespan import LifespanManager
from starlette.responses import PlainTextResponse
from app.core.concurrency_limiter import ConcurrencyLimiterMiddleware
from app.core.gateway_router import GatewayRouter

# Backend handler that holds the semaphore long enough to overlap
async def delayed_backend(scope, receive, send):
    await asyncio.sleep(0.2)
    await PlainTextResponse("OK")(scope, receive, send)

@pytest.mark.anyio
async def test_concurrency_limit_blocks_excess():
    backend_url = "http://fake-backend"
    route_table = {"/api": {"backend": backend_url}}

    transport = ASGITransport(app=delayed_backend)
    fake_client = httpx.AsyncClient(transport=transport, base_url=backend_url)

    app = GatewayRouter(route_table=route_table, client=fake_client)
    app = ConcurrencyLimiterMiddleware(app, max_concurrent=3)

    async with LifespanManager(app):
        async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # fire three requests and do not await them yet
            tasks = [asyncio.create_task(client.get("/api")) for _ in range(3)]

            # give them a moment to enter the middleware and acquire permits
            await asyncio.sleep(0.01)

            # this one should be shed since all three permits are in use
            res = await client.get("/api")
            assert res.status_code == 503
            assert res.headers.get("X-Concurrency-Limit") == "3"
            assert res.headers.get("X-Concurrency-Remaining") == "0"

            # now let the first three complete and verify they succeeded
            results = await asyncio.gather(*tasks)
            assert all(r.status_code == 200 for r in results)
