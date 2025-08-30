import asyncio
import httpx
from starlette.types import Scope, Receive, Send, Message
from starlette.responses import PlainTextResponse, Response
from typing import Optional
from urllib.parse import urljoin
from .routing_table import PathRouter


class GatewayRouter:
    def __init__(
        self,
        route_table: dict[str, str],
        timeout: float = 5.0,
        retries: int = 2,
        retry_delay: float = 0.1,
        client: Optional[httpx.AsyncClient] = None,
    ):
        self.router = PathRouter(route_table)
        self.retries = retries
        self.retry_delay = retry_delay
        self.client = client or httpx.AsyncClient(timeout=timeout)

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] == "lifespan":
            await self._handle_lifespan(scope, receive, send)
            return

        if scope["type"] != "http":
            await PlainTextResponse("Unsupported", status_code=400)(scope, receive, send)
            return

        await self._handle_http(scope, receive, send)

    async def _handle_http(self, scope: Scope, receive: Receive, send: Send):
        path = scope["path"]
        method = scope["method"]
        query = scope.get("query_string", b"").decode()

        backend_base = self.router.match(path)
        if not backend_base:
            await PlainTextResponse("Route not found", status_code=404)(scope, receive, send)
            return

        target_url = self._construct_target_url(backend_base, path, query)
        headers = self._extract_headers(scope)
        body = await self._read_body(receive)

        backend_response = await self._send_with_retries(method, target_url, headers, body)

        if backend_response is None:
            await PlainTextResponse(
                f"Upstream error after {self.retries} retries",
                status_code=502
            )(scope, receive, send)
            return

        await self._send_response(scope, receive, send, backend_response)

    def _construct_target_url(self, base: str, path: str, query: str) -> str:
        url = urljoin(base, path)
        return f"{url}?{query}" if query else url

    def _extract_headers(self, scope: Scope) -> dict[str, str]:
        headers = {k.decode(): v.decode() for k, v in scope.get("headers", [])}
        headers.pop("host", None)
        return headers

    async def _read_body(self, receive: Receive) -> bytes:
        body = b""
        more_body = True
        while more_body:
            message = await receive()
            body += message.get("body", b"")
            more_body = message.get("more_body", False)
        return body

    async def _send_with_retries(
        self,
        method: str,
        url: str,
        headers: dict[str, str],
        body: bytes
    ) -> Optional[httpx.Response]:
        attempt = 0
        while attempt <= self.retries:
            try:
                response = await self.client.request(
                    method=method,
                    url=url,
                    headers=headers,
                    content=body,
                )
                if response.status_code < 500:
                    return response
            except httpx.RequestError:
                pass
            attempt += 1
            if attempt <= self.retries:
                await asyncio.sleep(self.retry_delay)
        return None

    async def _send_response(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
        backend_response: httpx.Response
    ):
        await Response(
            content=backend_response.content,
            status_code=backend_response.status_code,
            headers=dict(backend_response.headers),
            media_type=backend_response.headers.get("content-type"),
        )(scope, receive, send)

    async def _handle_lifespan(self, scope: Scope, receive: Receive, send: Send):
        while True:
            message = await receive()
            if message["type"] == "lifespan.startup":
                await send({"type": "lifespan.startup.complete"})
            elif message["type"] == "lifespan.shutdown":
                await self.client.aclose()
                await send({"type": "lifespan.shutdown.complete"})
                return
