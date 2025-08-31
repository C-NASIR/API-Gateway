from starlette.types import ASGIApp, Scope, Receive, Send


class MountAdminFirst:
    def __init__(self, admin_app: ASGIApp, main_app: ASGIApp) -> None:
        self.admin_app = admin_app
        self.main_app = main_app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope["path"].startswith("/__"):
            await self.admin_app(scope, receive, send)
        else:
            await self.main_app(scope, receive, send)
