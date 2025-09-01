import pytest
import logging
from asgi_lifespan import LifespanManager
from app.core.gateway_router import GatewayRouter

@pytest.mark.anyio
async def test_gateway_graceful_shutdown_logs(caplog):
    caplog.set_level(logging.INFO)

    app = GatewayRouter()

    async with LifespanManager(app):
        pass  # Simulate full lifecycle

    assert "[gateway] Shutdown complete. All resources closed." in caplog.text
