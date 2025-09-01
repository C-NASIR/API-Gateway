import pytest
import httpx
from httpx import ASGITransport
from asgi_lifespan import LifespanManager
from app.core.gateway_router import GatewayRouter
from app.core.path_router import PathRouter
from tests.fixtures.mock_backends import fake_users_backend

@pytest.mark.anyio
async def test_proxy_users_route_returns_mocked_response():
    backend_url = "http://fake-users"
    route_table={"/users": {"backend": backend_url}}
    path_router = PathRouter(route_table=route_table)

    transport = ASGITransport(app=fake_users_backend)
    fake_client = httpx.AsyncClient(transport=transport, base_url=backend_url)

    app = GatewayRouter(path_router=path_router, client=fake_client)

    async with LifespanManager(app):
        test_client = httpx.AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test")
        res = await test_client.get("/users/")
        assert res.status_code == 200
        assert res.json() == {"status": "ok", "source": "users"}
