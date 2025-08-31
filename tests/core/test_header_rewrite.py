import pytest
import httpx
from httpx import ASGITransport
from asgi_lifespan import LifespanManager
from starlette.responses import JSONResponse
from app.core.gateway_router import GatewayRouter
from app.core.trace import TraceMiddleware


# Simple backend that echoes headers
async def echo_headers_backend(scope, receive, send):
    headers = {k.decode(): v.decode() for k, v in scope["headers"]}
    await JSONResponse(headers)(scope, receive, send)


@pytest.mark.anyio
async def test_gateway_rewrites_and_forwards_headers():
    backend_url = "http://fake-backend"
    route_table = {"/api": {"backend": backend_url}}

    # Fake backend app behind the gateway
    transport = ASGITransport(app=echo_headers_backend)
    fake_client = httpx.AsyncClient(transport=transport, base_url=backend_url)

    # Gateway with TraceMiddleware + GatewayRouter with header rewriting
    app = TraceMiddleware(
        GatewayRouter(
            route_table=route_table,
            client=fake_client
        )
    )

    async with LifespanManager(app):
        async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Client sends sensitive headers
            res = await client.get(
                "/api",
                headers={
                    "Authorization": "Bearer abc123",
                    "Cookie": "sessionid=xyz456",
                    "X-Custom": "my-value"
                }
            )

            backend_headers = res.json()

            # These sensitive headers should have been stripped
            assert "authorization" not in backend_headers
            assert "cookie" not in backend_headers

            # TraceMiddleware should add a trace ID
            assert "x-trace-id" in backend_headers
            trace_id = backend_headers["x-trace-id"]
            assert trace_id and isinstance(trace_id, str)

            # Gateway should inject this custom header
            assert backend_headers.get("x-gateway") == "my-api-gateway"

            # This client-defined header should still go through
            assert backend_headers.get("x-custom") == "my-value"
