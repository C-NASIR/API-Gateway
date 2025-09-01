
import time
import logging
import json
from redis.asyncio import Redis
from typing import Any
from starlette.types import ASGIApp, Scope, Receive, Send
from starlette.responses import PlainTextResponse, JSONResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST
from app.core.metrics import render_prometheus_metrics
from app.core.gateway_router import GatewayRouter

logger = logging.getLogger(__name__)

class AdminRouter:
    def __init__(self, router: GatewayRouter, redis: Redis = None) -> None:
        self.router = router
        self.redis = redis

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
        elif path == "/__metrics":
            await self.metrics(scope, receive, send)
        elif path == "/__reload" and scope.get("method", "") == "POST":
            await self.reload_config(scope, receive, send)
        else:
            await PlainTextResponse("Not Found", status_code=404)(scope, receive, send)

    async def health(self, scope: Scope, receive: Receive, send: Send) -> None:
        await PlainTextResponse("OK")(scope, receive, send)

    async def routes(self, scope: Scope, receive: Receive, send: Send) -> None:
        await JSONResponse(self.router.path_router.route_table)(scope, receive, send)

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
    

    async def metrics(self, scope: Scope, receive: Receive, send: Send) -> None:
        data, content_type = render_prometheus_metrics()
        await Response( content=data, media_type=content_type)(scope, receive, send)


    async def reload_config(self, scope: Scope, receive: Receive, send: Send) -> None:
        if time.time() - self.router.path_router.last_reload < 10:
            return await JSONResponse({"error": "Reload too frequent"},
                                       status_code=429)(scope, receive, send)

        try:
            print('before')
            raw_json = await self.redis.get("route_config")
            print('after', raw_json)
            new_config = json.loads(raw_json)
            await self.router.path_router.update_route_table(new_config)
            self.router.path_router.last_reload = time.time()
            return await JSONResponse({"status": "Reloaded", "routes":
                                 list(new_config.keys())})(scope, receive, send)
        except Exception as e:
            logger.error(f"Reload failed: {e}")
            return await JSONResponse({"error": "Reload failed"},
                                      status_code=500)(scope, receive, send)
