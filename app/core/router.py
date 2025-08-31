import asyncio
import httpx
import logging
from starlette.types import Scope, Receive, Send, Message
from starlette.responses import PlainTextResponse, Response
from typing import Optional
from urllib.parse import urljoin
from .routing_table import PathRouter
from .circuit_breaker import CircuitBreaker
from .header_rewrite import HeaderRewriter
from .trace import trace_id_var

logger = logging.getLogger(__name__)


class GatewayRouter:
    def __init__(
        self,
        route_table: dict[str, str],
        timeout: float = 5.0,
        retries: int = 2,
        retry_delay: float = 0.1,
        client: Optional[httpx.AsyncClient] = None,
        circuit_breaker: Optional[CircuitBreaker] = None,
        header_rewriter: Optional[HeaderRewriter] = None,
    ):
        self.router = PathRouter(route_table)
        self.retries = retries
        self.retry_delay = retry_delay
        self.client = client or httpx.AsyncClient(timeout=timeout)
        self.circuit_breaker = circuit_breaker or CircuitBreaker()

        self.header_rewriter = header_rewriter or HeaderRewriter(
            remove=["authorization", "cookie"],
            set_={"x-gateway": "my-api-gateway"}
        )

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

        logger.info(f"Incoming request: {method} {path}?{query}")

        backend_base = self.router.match(path)
        if not backend_base:
            logger.warning(f"No route match for {path}")
            await PlainTextResponse("Route not found", status_code=404)(scope, receive, send)
            return

        target_url = self._construct_target_url(backend_base, path, query)
        logger.info(f"Proxying request to: {target_url}")

        headers = self._extract_headers(scope)
        body = await self._read_body(receive)

        backend_response = await self._send_with_retries(method, target_url, headers, body)

        if backend_response is None:
            logger.error(f"Upstream failure after {self.retries} retries for {target_url}")
            await PlainTextResponse(
                f"Upstream error after {self.retries} retries",
                status_code=502
            )(scope, receive, send)
            return

        if isinstance(backend_response, Response):  # circuit breaker shortcut
            logger.warning(f"Circuit breaker blocked request to {target_url}")
            await backend_response(scope, receive, send)
            return

        logger.info(f"Successful response from backend: \
                    {target_url} ({backend_response.status_code})")
        await self._send_response(scope, receive, send, backend_response)

    def _construct_target_url(self, base: str, path: str, query: str) -> str:
        url = urljoin(base, path)
        return f"{url}?{query}" if query else url

    def _extract_headers(self, scope: Scope) -> dict[str, str]:
        raw_headers = scope.get("headers", [])
        rewritten = self.header_rewriter.rewrite(raw_headers, scope, trace_id_var.get())
        rewritten.pop("host", None)
        return rewritten

    async def _read_body(self, receive: Receive) -> bytes:
        body = b""
        more_body = True
        while more_body:
            message = await receive()
            body += message.get("body", b"")
            more_body = message.get("more_body", False)
        return body

    async def _send_with_retries(self,
        method: str,
        url: str,
        headers: dict[str, str],
        body: bytes
    ) -> Optional[httpx.Response]:
        
        backend = url.split("/")[2]

        if not self.circuit_breaker.allow_request(backend):
            logger.warning(f"Circuit breaker is OPEN for {backend}, request blocked.")
            return PlainTextResponse(
                "Upstream error after circuit breaker opened",
                status_code=502,
                headers={"X-Circuit-Open": "true"}
            )

        attempt = 0
        while attempt <= self.retries:
            try:
                logger.info(f"Attempt {attempt+1} to {url}")
                response = await self.client.request(
                    method=method,
                    url=url,
                    headers=headers,
                    content=body,
                )
                if response.status_code < 500:
                    self.circuit_breaker.record_success(backend)
                    return response
            except httpx.RequestError as e:
                logger.error(f"Request error to {url}: {str(e)}")

            self.circuit_breaker.record_failure(backend)
            attempt += 1
            if attempt <= self.retries:
                logger.info(f"Retrying after delay ({self.retry_delay}s)")
                await asyncio.sleep(self.retry_delay)

        logger.error(f"All retries failed for {url}")
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
