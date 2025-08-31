import time
from starlette.types import ASGIApp, Scope, Receive, Send
from starlette.responses import PlainTextResponse


class InMemoryRateLimiter:
    def __init__(self, limit: int, window_seconds: int):
        self.limit = limit
        self.window = window_seconds
        self.buckets = {}  # identity -> [start_time, count]

    def allow(self, identity: str) -> bool:
        now = int(time.time())
        bucket = self.buckets.get(identity)

        if not bucket or now - bucket[0] >= self.window:
            self.buckets[identity] = [now, 1]
            return True

        if bucket[1] < self.limit:
            bucket[1] += 1
            return True

        return False

    def retry_after(self, identity: str) -> int:
        bucket = self.buckets.get(identity)
        if not bucket:
            return 0
        return max(0, self.window - (int(time.time()) - bucket[0]))

    def remaining(self, identity: str) -> int:
        bucket = self.buckets.get(identity)
        if not bucket:
            return self.limit
        return max(0, self.limit - bucket[1])


class RateLimitMiddleware:
    def __init__(self, app: ASGIApp, limiter: InMemoryRateLimiter):
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
        remaining = self.limiter.remaining(identity)
        headers = {
            "RateLimit-Limit": str(limit),
            "RateLimit-Remaining": str(remaining),
        }

        if not self.limiter.allow(identity):
            retry = self.limiter.retry_after(identity)
            headers["Retry-After"] = str(retry)
            response = PlainTextResponse("Too Many Requests", status_code=429,headers=headers)
            await response(scope, receive, send)
            return

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                message.setdefault("headers", [])
                def add_header(name, value):
                    message["headers"].append((name.encode(), value.encode()))
                add_header("RateLimit-Limit", str(limit))
                add_header("RateLimit-Remaining", str(self.limiter.remaining(identity)))
            await send(message)

        await self.app(scope, receive, send_with_headers)
