
from app.core.gateway_router import GatewayRouter
from app.core.rate_limiter import RateLimitMiddleware, InMemoryRateLimiter
from app.core.trace import TraceMiddleware
from app.core.logging_setup import configure_logging
from app.core.concurrency_limiter import ConcurrencyLimiterMiddleware
from app.config.routes import ROUTE_TABLE
import uvicorn

configure_logging()

app = GatewayRouter(route_table=ROUTE_TABLE)
app = RateLimitMiddleware(app, InMemoryRateLimiter(limit=5, window_seconds=10))
app = ConcurrencyLimiterMiddleware(app, max_concurrent=100)
app = TraceMiddleware(app)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
