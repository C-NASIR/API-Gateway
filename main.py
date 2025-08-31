from app.core.gateway_router import GatewayRouter
from app.core.rate_limiter import RateLimitMiddleware, InMemoryRateLimiter
from app.core.trace import TraceMiddleware
from app.core.logging_setup import configure_logging
from app.core.concurrency_limiter import ConcurrencyLimiterMiddleware
from app.core.admin_router import AdminRouter
from app.core.mount_admin_first import MountAdminFirst
from app.config.routes import ROUTE_TABLE
import uvicorn

configure_logging()

# Base gateway app
gateway_app = GatewayRouter(route_table=ROUTE_TABLE)

# Apply middlewares
gateway_app = RateLimitMiddleware(gateway_app, InMemoryRateLimiter(limit=5, window_seconds=10))
gateway_app = ConcurrencyLimiterMiddleware(gateway_app, max_concurrent=100)
gateway_app = TraceMiddleware(gateway_app)

# Add admin routes with prefix /__
admin_app = AdminRouter(gateway_app)
app = MountAdminFirst(admin_app, gateway_app)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
