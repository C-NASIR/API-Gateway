
from app.core.router import GatewayRouter
from app.core.rate_limit import RateLimitMiddleware, InMemoryRateLimiter
from app.config.routes import ROUTE_TABLE
import uvicorn

app = GatewayRouter(route_table=ROUTE_TABLE)
app = RateLimitMiddleware(app, InMemoryRateLimiter(limit=5, window_seconds=10))

app = GatewayRouter()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
