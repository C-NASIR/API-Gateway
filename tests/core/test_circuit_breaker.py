import pytest
import httpx
from httpx import ASGITransport
from asgi_lifespan import LifespanManager
from starlette.responses import PlainTextResponse, JSONResponse
from app.core.router import GatewayRouter
from app.core.circuit_breaker import CircuitBreaker  # wherever you put the class


class FlakyBackend:
    """
    A fake backend that fails a few times, then recovers.
    """
    def __init__(self, fail_times: int):
        self.fail_times = fail_times
        self.calls = 0

    async def __call__(self, scope, receive, send):
        self.calls += 1
        if self.calls <= self.fail_times:
            await PlainTextResponse("Internal Error", status_code=500)(scope, receive, send)
        else:
            await JSONResponse({"status": "ok"})(scope, receive, send)


@pytest.mark.anyio
async def test_circuit_breaker_resets_after_recovery():
    backend_url = "http://fake-backend"
    route_table = {"/api": backend_url}

    # Backend fails 2 times, then starts working
    flaky_backend = FlakyBackend(fail_times=2)
    transport = ASGITransport(app=flaky_backend)
    fake_client = httpx.AsyncClient(transport=transport, base_url=backend_url)

    # Circuit breaker opens after 2 failures, recovers after 0.1s
    breaker = CircuitBreaker(failure_threshold=2, recovery_time=0.1)

    app = GatewayRouter(
        route_table=route_table,
        client=fake_client,
        circuit_breaker=breaker,
        retries=0  # Disable retries to test circuit breaker directly
    )

    async with LifespanManager(app):
        client = httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

        # First 2 requests fail and trigger the circuit to open
        for _ in range(2):
            res = await client.get("/api")
            assert res.status_code == 502

        # Circuit should now be open and block this request (fail fast)
        res = await client.get("/api")
        assert res.status_code == 502
        assert res.headers.get("X-Circuit-Open") == "true"
        assert "circuit breaker" in res.text.lower()

        # Wait for the circuit to reset
        import asyncio
        await asyncio.sleep(0.11)

        # Circuit should allow request, and backend has recovered
        res = await client.get("/api")
        assert res.status_code == 200
        assert res.json() == {"status": "ok"}
