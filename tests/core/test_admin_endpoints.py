import pytest
import httpx
from httpx import ASGITransport
from asgi_lifespan import LifespanManager
from starlette.types import Scope, Receive, Send
from starlette.responses import PlainTextResponse

from app.core.gateway_router import GatewayRouter
from app.core.admin_router import AdminRouter
from app.core.mount_admin_first import MountAdminFirst
from app.core.path_router import PathRouter

ROUTE_TABLE = {
    "/api": "http://backend1.local",
    "/auth": {
        "backend": "http://backend2.local",
        "retries": 2,
        "timeout": 3.0
    }
}

# Fake backend that always returns 200
async def fake_backend(scope: Scope, receive: Receive, send: Send):
    await PlainTextResponse("Backend OK")(scope, receive, send)

@pytest.mark.anyio
async def test_admin_endpoints():
    transport = ASGITransport(app=fake_backend)
    fake_client = httpx.AsyncClient(transport=transport, base_url="http://backend1.local")

    path_router = PathRouter(route_table=ROUTE_TABLE)
    gateway = GatewayRouter(path_router, client=fake_client)
    admin = AdminRouter(gateway)
    app = MountAdminFirst(admin, gateway)

    async with LifespanManager(app):
        async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            res = await client.get("/__health")
            assert res.status_code == 200
            assert "ok" in res.text.lower()

            res = await client.get("/__routes")
            assert res.status_code == 200
            print(res.json())
            assert "/api" in res.json()
            assert "/auth" in res.json()

            res = await client.get("/__circuit")
            assert res.status_code == 200
            assert isinstance(res.json(), dict)

            res = await client.get("/__limits")
            assert res.status_code == 200
            assert isinstance(res.json(), dict)
