import pytest
from asgi_lifespan import LifespanManager
from app.core.gateway_router import GatewayRouter

@pytest.mark.anyio
async def test_gateway_lifecycle_runs_without_error():
    app = GatewayRouter()

    # This ensures both startup and shutdown complete without raising exceptions
    async with LifespanManager(app):
        pass