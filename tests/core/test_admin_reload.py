import pytest
import httpx
import json
import fakeredis
from httpx import ASGITransport
from asgi_lifespan import LifespanManager
from starlette.types import Scope, Receive, Send
from starlette.responses import PlainTextResponse

from app.core.gateway_router import GatewayRouter
from app.core.path_router import PathRouter
from app.core.admin_router import AdminRouter
from app.core.mount_admin_first import MountAdminFirst

# Simulated backend response
async def fake_backend(scope: Scope, receive: Receive, send: Send):
    await PlainTextResponse("Backend OK")(scope, receive, send)

@pytest.mark.anyio
async def test_admin_reload_updates_route_table():
    # 1. Start with an empty route table
    path_router = PathRouter(route_table={})

    # 2. Setup backend
    backend_url = "http://backend1.local"
    transport = ASGITransport(app=fake_backend)
    fake_client = httpx.AsyncClient(transport=transport, base_url=backend_url)

    # 3. Setup gateway
    gateway = GatewayRouter(path_router=path_router, client=fake_client)

    # 4. Fake Redis setup
    new_route_config = {
        "/api": {"backend": backend_url}
    }
    fake_redis = fakeredis.FakeAsyncRedis(decode_responses=True)
    await fake_redis.set("route_config", json.dumps(new_route_config))

    # 5. Mount app with admin
    admin = AdminRouter(router=gateway, redis=fake_redis)
    app = MountAdminFirst(admin, gateway)

    # 6. Test reload
    async with LifespanManager(app):
        async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Call the reload endpoint
            reload_res = await client.post("/__reload")
            assert reload_res.status_code == 200
            assert "reloaded" in reload_res.text.lower()

            # Confirm route was added and works
            route_res = await client.get("/api")
            assert route_res.status_code == 200
            assert route_res.text == "Backend OK"
