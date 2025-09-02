from starlette.responses import PlainTextResponse
from starlette.types import ASGIApp, Scope, Receive, Send
from app.core.redis_rate_limiter import RedisRateLimiter
from app.core.inmemory_rate_limiter import InMemoryRateLimiter

class RateLimitMiddleware:
    def __init__(self, app: ASGIApp, limiter: RedisRateLimiter | InMemoryRateLimiter):
        self.app = app
        self.limiter = limiter

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "/")
        client = scope.get("client")
        ip = client[0] if client else "unknown"
        identity = f"{ip}:{path}"

        limit = self.limiter.limit
        remaining = await self.limiter.remaining(identity)

        headers = {
            "RateLimit-Limit": str(limit),
            "RateLimit-Remaining": str(remaining),
        }

        allowed, retry_after = await self.limiter.allow(identity)
        if not allowed:
            headers["Retry-After"] = str(retry_after)
            response = PlainTextResponse("Too Many Requests", status_code=429, headers=headers)
            await response(scope, receive, send)
            return

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                message.setdefault("headers", [])
                def add_header(name, value):
                    message["headers"].append((name.encode(), value.encode()))
                add_header("RateLimit-Limit", str(limit))
                remaining = await self.limiter.remaining(identity)
                add_header("RateLimit-Remaining", str(remaining))
            await send(message)

        await self.app(scope, receive, send_with_headers)
