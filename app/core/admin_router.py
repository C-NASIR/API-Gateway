from typing import Any
from starlette.types import ASGIApp, Scope, Receive, Send
from starlette.responses import PlainTextResponse, JSONResponse
from app.core.gateway_router import GatewayRouter


class AdminRouter:
    def __init__(self, router: GatewayRouter) -> None:
        self.router = router

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        path = scope.get("path", "")
        if path == "/__health":
            await self.health(scope, receive, send)
        elif path == "/__routes":
            await self.routes(scope, receive, send)
        elif path == "/__circuit":
            await self.circuit(scope, receive, send)
        elif path == "/__limits":
            await self.limits(scope, receive, send)
        else:
            await PlainTextResponse("Not Found", status_code=404)(scope, receive, send)

    async def health(self, scope: Scope, receive: Receive, send: Send) -> None:
        await PlainTextResponse("OK")(scope, receive, send)

    async def routes(self, scope: Scope, receive: Receive, send: Send) -> None:
        await JSONResponse(self.router.router.route_table)(scope, receive, send)

    async def circuit(self, scope: Scope, receive: Receive, send: Send) -> None:
        circuit_state = self.router.circuit_breaker.get_status()
        await JSONResponse(circuit_state)(scope, receive, send)

    async def limits(self, scope: Scope, receive: Receive, send: Send) -> None:
        rate_data: dict[str, Any] = {}
        concurrency_data: dict[str, Any] = {}

        if hasattr(self.router, "rate_limiter") and hasattr(self.router.rate_limiter, "stats"):
            rate_data = self.router.rate_limiter.stats()

        if hasattr(self.router, "concurrency_limit"):
            concurrency_data["max"] = getattr(self.router, "concurrency_limit")
        if hasattr(self.router, "in_flight"):
            concurrency_data["in_flight"] = getattr(self.router, "in_flight")

        data = {
            "rate_limit": rate_data,
            "concurrency_limit": concurrency_data
        }

        await JSONResponse(data)(scope, receive, send)
