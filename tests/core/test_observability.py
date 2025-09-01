import pytest
import httpx
import uuid
import logging
from httpx import ASGITransport
from app.core.gateway_router import GatewayRouter
from asgi_lifespan import LifespanManager
from starlette.responses import JSONResponse, PlainTextResponse
from app.core.trace import TraceMiddleware, trace_id_var
from app.core.path_router import PathRouter


# ----------------------------
# Helpers
# ----------------------------

def build_gateway_app(backend_app, route_table, backend_url):
    transport = ASGITransport(app=backend_app)
    fake_client = httpx.AsyncClient(transport=transport, base_url=backend_url)
    path_router = PathRouter(route_table=route_table)
    return TraceMiddleware(GatewayRouter(path_router, client=fake_client))


# ----------------------------
# Backends
# ----------------------------

# Simple backend that returns the trace ID it received
async def echo_trace_id_backend(scope, receive, send):
    headers = dict((k.decode(), v.decode()) for k, v in scope["headers"])
    print("Backend received headers:", headers)
    trace_id = headers.get("x-trace-id", "missing")
    await JSONResponse({"trace_id": trace_id}, status_code=200)(scope, receive, send)

# Backend that logs with trace ID in scope
async def backend_with_logging(scope, receive, send):
    logger = logging.getLogger("test-observability")
    logger.info(f"Log triggered by trace ID: {trace_id_var.get()}")
    await PlainTextResponse("logged")(scope, receive, send)


# ----------------------------
# Tests
# ----------------------------

@pytest.mark.anyio
async def test_trace_id_is_injected_by_gateway():
    backend_url = "http://fake-users"
    route_table = {"/api": {"backend": backend_url}}
    app = build_gateway_app(echo_trace_id_backend, route_table, backend_url)

    async with LifespanManager(app):
        async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            res = await client.get("/api")
            trace_id = res.headers.get("X-Trace-ID")

            print("Response headers:", res.json())
            assert res.status_code == 200
            assert trace_id is not None
            assert uuid.UUID(trace_id)
            assert res.json()["trace_id"] == trace_id


@pytest.mark.anyio
async def test_trace_id_is_preserved_if_sent_by_client():
    backend_url = "http://fake-users"
    route_table = {"/api": {"backend": backend_url}}
    app = build_gateway_app(echo_trace_id_backend, route_table, backend_url)

    async with LifespanManager(app):
        async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            given_id = str(uuid.uuid4())
            res = await client.get("/api", headers={"X-Trace-ID": given_id})

            assert res.status_code == 200
            assert res.headers["X-Trace-ID"] == given_id
            assert res.json()["trace_id"] == given_id


@pytest.mark.anyio
async def test_trace_id_appears_in_logs(caplog):
    caplog.set_level(logging.INFO, logger="test-observability")

    backend_url = "http://fake-users"
    route_table = {"/api": {"backend": backend_url}}
    app = build_gateway_app(backend_with_logging, route_table, backend_url)

    async with LifespanManager(app):
        async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            res = await client.get("/api")
            assert res.status_code == 200

    trace_id = res.headers.get("X-Trace-ID")
    assert trace_id is not None
    assert f"Log triggered by trace ID: {trace_id}" in caplog.text
