import asyncio
import logging
from starlette.types import ASGIApp, Scope, Receive, Send
from starlette.responses import PlainTextResponse

logger = logging.getLogger("gateway.concurrency.limiter")

class ConcurrencyLimiterMiddleware:
    def __init__(self, app: ASGIApp, max_concurrent: int = 100):
        self.app = app
        self.max_concurrent = max_concurrent
        self._in_flight = 0
        self._lock = asyncio.Lock()

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # fail fast admission control
        async with self._lock:
            if self._in_flight >= self.max_concurrent:
                await PlainTextResponse(
                    "Too many concurrent requests",
                    status_code=503,
                    headers={
                        "X-Concurrency-Limit": str(self.max_concurrent),
                        "X-Concurrency-Remaining": "0",
                    },
                )(scope, receive, send)
                return
            self._in_flight += 1

        try:
            # optionally add headers on success as well
            async def send_with_headers(message):
                if message["type"] == "http.response.start":
                    remaining = max(0, self.max_concurrent - self._in_flight)
                    headers = message.setdefault("headers", [])
                    headers.append((b"x-concurrency-limit", str(self.max_concurrent).encode()))
                    headers.append((b"x-concurrency-remaining", str(remaining).encode()))
                await send(message)

            await self.app(scope, receive, send_with_headers)
        finally:
            async with self._lock:
                self._in_flight -= 1
