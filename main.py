import uvicorn
import os
from dotenv import load_dotenv
from redis import asyncio as redis
from app.core.gateway_router import GatewayRouter
from app.core.rate_limiter import RateLimitMiddleware, InMemoryRateLimiter
from app.core.trace import TraceMiddleware
from app.core.logging_setup import configure_logging
from app.core.concurrency_limiter import ConcurrencyLimiterMiddleware
from app.core.admin_router import AdminRouter
from app.core.mount_admin_first import MountAdminFirst

# Load environment variables from .env file
load_dotenv()
configure_logging()

# Access the variables
redis_host = os.getenv("REDIS_HOST")
redis_port = os.getenv("REDIS_PORT")

redis_client = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)

# Base gateway app
core_gateway = GatewayRouter()

# Apply middlewares to a wrapped version
gateway_app = RateLimitMiddleware(core_gateway, InMemoryRateLimiter(limit=5, window_seconds=10))
gateway_app = ConcurrencyLimiterMiddleware(gateway_app, max_concurrent=100)
gateway_app = TraceMiddleware(gateway_app)

# Admin gets direct access to the unwrapped GatewayRouter instance
admin_app = AdminRouter(core_gateway, redis=redis_client)

# Mount admin + gateway stack
app = MountAdminFirst(admin_app, gateway_app)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
