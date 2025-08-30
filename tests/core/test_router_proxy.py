import pytest
import httpx
from httpx import ASGITransport
from asgi_lifespan import LifespanManager
from app.core.router import GatewayRouter
from tests.fixtures.mock_backends import fake_users_backend


@pytest.mark.anyio
async def test_proxy_users_route_returns_mocked_response():
    transport = ASGITransport(app=fake_users_backend)
    backend_url = "http://fake-users"
    fake_client = httpx.AsyncClient(transport=transport, base_url=backend_url)

    app = GatewayRouter(
        route_table={"/users": backend_url}, client=fake_client)

    async with LifespanManager(app):
        test_client = httpx.AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test")
        res = await test_client.get("/users/")
        assert res.status_code == 200
        assert res.json() == {"status": "ok", "source": "users"}
