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
core_gateway = GatewayRouter(route_table=ROUTE_TABLE)

# Apply middlewares to a wrapped version
gateway_app = RateLimitMiddleware(core_gateway, InMemoryRateLimiter(limit=5, window_seconds=10))
gateway_app = ConcurrencyLimiterMiddleware(gateway_app, max_concurrent=100)
gateway_app = TraceMiddleware(gateway_app)

# Admin gets direct access to the unwrapped GatewayRouter instance
admin_app = AdminRouter(core_gateway)

# Mount admin + gateway stack
app = MountAdminFirst(admin_app, gateway_app)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
