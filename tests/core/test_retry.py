import pytest
import httpx
from httpx import ASGITransport
from asgi_lifespan import LifespanManager
from starlette.responses import JSONResponse, PlainTextResponse
from app.core.router import GatewayRouter

class FlakyBackend:
    def __init__(self, fail_times: int):
        self.fail_times = fail_times
        self.call_count = 0

    async def __call__(self, scope, receive, send):
        self.call_count += 1
        if self.call_count <= self.fail_times:
            print(f'failing one ', self.call_count)
            await PlainTextResponse("backend failure", status_code=500)(scope, receive, send)
        else:
            print(f'succeeding one ', self.call_count)
            await JSONResponse({"status": "success"})(scope, receive, send)


@pytest.mark.anyio
async def test_retries_then_success():
    backend_url = "http://fake-backend"
    route_table = {"/test": backend_url}
    backend = FlakyBackend(fail_times=1)  # fail once, then succeed
    transport = ASGITransport(app=backend)

    fake_client = httpx.AsyncClient(transport=transport, base_url=backend_url)

    app = GatewayRouter(route_table, client=fake_client, retries=2)

    async with LifespanManager(app):
        client = httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
        res = await client.get("/test")
        assert res.status_code == 200
        assert res.json() == {"status": "success"}


@pytest.mark.anyio
async def test_retries_exhausted_then_fail():
    backend = FlakyBackend(fail_times=5)  # fail too many times
    transport = ASGITransport(app=backend)
    backend_url = "http://fake-backend"
    route_table = {"/test": backend_url}

    fake_client = httpx.AsyncClient(transport=transport, base_url=backend_url)

    app = GatewayRouter(route_table, client=fake_client, retries=2)

    async with LifespanManager(app):
        client = httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
        res = await client.get("/test")
        assert res.status_code == 502
        assert "Upstream error" in res.text
