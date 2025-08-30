from starlette.responses import JSONResponse
from starlette.requests import Request


async def fake_users_backend(scope, receive, send):
    request = Request(scope, receive)
    await JSONResponse({"status": "ok", "source": "users"})(scope, receive, send)


async def fake_orders_backend(scope, receive, send):
    request = Request(scope, receive)
    await JSONResponse({"status": "ok", "source": "orders"})(scope, receive, send)
