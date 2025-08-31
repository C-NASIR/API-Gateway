import pytest
import httpx
from httpx import ASGITransport
from starlette.responses import JSONResponse
from asgi_lifespan import LifespanManager
from app.core.gateway_router import GatewayRouter


# Fake backend that returns received headers as JSON
async def echo_headers_backend(scope, receive, send):
    headers = {k.decode(): v.decode() for k, v in scope["headers"]}
    await JSONResponse({"headers": headers})(scope, receive, send)


@pytest.mark.anyio
async def test_custom_route_config_with_inline_header_policy():
    route_table = {
        "/api": {
            "backend": "http://fake-backend",
        },
        "/auth": {
            "backend": "http://fake-backend",
            "retries": 5,
            "retry_delay": 0.2,
            "timeout": 2.0,
            "header_policy": {
                "remove": ["x-remove-this"],
                "set": {"x-api": "auth-service"},
                "append": {"x-version": "1.0"}
            }
        }
    }

    # Stub backend setup
    transport = ASGITransport(app=echo_headers_backend)
    fake_client = httpx.AsyncClient(transport=transport, base_url="http://fake-backend")

    app = GatewayRouter(route_table=route_table, client=fake_client)

    async with LifespanManager(app):
        async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Send request to the /auth route with a header that should be removed
            res = await client.get("/auth", headers={"x-remove-this": "bad"})

            assert res.status_code == 200
            headers = res.json()["headers"]

            # Check rewrites
            assert "x-remove-this" not in headers
            assert headers["x-api"] == "auth-service"
            assert headers["x-version"] == "1.0"
