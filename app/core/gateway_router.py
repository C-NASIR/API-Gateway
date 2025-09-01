import asyncio
import httpx
import time
import logging
from starlette.types import Scope, Receive, Send, Message
from starlette.responses import PlainTextResponse, Response
from typing import Optional, Any
from urllib.parse import urljoin
from app.core.metrics import REQUEST_COUNT, REQUEST_DURATION, ACTIVE_REQUESTS
from .routing_table import PathRouter
from .circuit_breaker import CircuitBreaker
from .header_rewriter import HeaderRewriter
from .trace import trace_id_var


logger = logging.getLogger(__name__)


class GatewayRouter:
    def __init__(
        self,
        route_table: dict[str, Any],
        timeout: float = 5.0,
        retries: int = 2,
        retry_delay: float = 0.1,
        client: Optional[httpx.AsyncClient] = None,
        circuit_breaker: Optional[CircuitBreaker] = None,
        header_rewriter: Optional[HeaderRewriter] = None,
    ):
        self.router = PathRouter(route_table)
        self.default_retries = retries
        self.default_retry_delay = retry_delay
        self.default_timeout = timeout
        self.default_header_rewriter = header_rewriter or HeaderRewriter(
            remove=["authorization", "cookie"],
            set_={"x-gateway": "my-api-gateway"}
        )
        self.client = client or httpx.AsyncClient(timeout=timeout)
        self.circuit_breaker = circuit_breaker or CircuitBreaker()

        self.cleanup_callbacks: list[callable] = []
        self.add_cleanup_callback(self.client.aclose)

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

        backend_base, config = self.router.match(path)
        if not backend_base:
            logger.warning(f"No route match for {path}")
            await PlainTextResponse("Route not found", status_code=404)(scope, receive, send)
            return

        retries = config.get("retries", self.default_retries)
        retry_delay = config.get("retry_delay", self.default_retry_delay)
        timeout = config.get("timeout", self.default_timeout)
        header_policy = config.get("header_policy", None)

        header_rewriter = self._get_header_rewriter(header_policy)
        target_url = self._construct_target_url(backend_base, path, query)
        logger.info(f"Proxying request to: {target_url}")

        headers = self._extract_headers(scope, header_rewriter)
        body = await self._read_body(receive)

        ACTIVE_REQUESTS.inc()
        start = time.time()
        try:
            backend_response = await self._send_with_retries(
                method, target_url, headers, body,
                retries=retries, retry_delay=retry_delay, timeout=timeout
            )
        finally:
            duration = time.time() - start
            ACTIVE_REQUESTS.dec()
            REQUEST_DURATION.labels(route=path).observe(duration)

        if backend_response is None:
            REQUEST_COUNT.labels(method=method, route=path, status="502").inc()
            logger.error(f"Upstream failure after {retries} retries for {target_url}")
            await PlainTextResponse(
                f"Upstream error after {retries} retries",
                status_code=502
            )(scope, receive, send)
            return

        if isinstance(backend_response, Response):  # circuit breaker shortcut
            status_code = backend_response.status_code
            REQUEST_COUNT.labels(method=method, route=path, status=str(status_code)).inc()
            logger.warning(f"Circuit breaker blocked request to {target_url}")
            await backend_response(scope, receive, send)
            return

        REQUEST_COUNT.labels(method=method, route=path,
                             status=str(backend_response.status_code)).inc()
        logger.info(f"Successful response from backend: \
                    {target_url} ({backend_response.status_code})")
        await self._send_response(scope, receive, send, backend_response)

    def _get_header_rewriter(self, policy: dict | None) -> HeaderRewriter:
        if not policy:
            return self.default_header_rewriter
        mod = {k if k != "set" else "set_": v for k, v in policy.items()}
        return HeaderRewriter(**mod)
    
    def _construct_target_url(self, base: str, path: str, query: str) -> str:
        url = urljoin(base, path)
        return f"{url}?{query}" if query else url

    def _extract_headers(self, scope: Scope, header_rewriter: HeaderRewriter) -> dict[str, str]:
        raw_headers = scope.get("headers", [])
        rewritten = header_rewriter.rewrite(raw_headers, scope, trace_id_var.get())
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

    async def _send_with_retries(
        self,
        method: str,
        url: str,
        headers: dict[str, str],
        body: bytes,
        retries: int,
        retry_delay: float,
        timeout: float
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
        while attempt <= retries:
            try:
                logger.info(f"Attempt {attempt+1} to {url}")
                response = await self.client.request(
                    method=method,
                    url=url,
                    headers=headers,
                    content=body,
                    timeout=timeout or self.default_timeout
                )
                if response.status_code < 500:
                    self.circuit_breaker.record_success(backend)
                    return response
            except httpx.RequestError as e:
                logger.error(f"Request error to {url}: {str(e)}")

            self.circuit_breaker.record_failure(backend)
            attempt += 1
            if attempt <= retries:
                logger.info(f"Retrying after delay ({retry_delay}s)")
                await asyncio.sleep(retry_delay)

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

    def add_cleanup_callback(self, cb: callable) -> None:
        self.cleanup_callbacks.append(cb)

    async def _handle_lifespan(self, scope: Scope, receive: Receive, send: Send):
        while True:
            message = await receive()
            if message["type"] == "lifespan.startup":
                await send({"type": "lifespan.startup.complete"})
            elif message["type"] == "lifespan.shutdown":
                for cb in self.cleanup_callbacks:
                    result = cb()
                    if asyncio.iscoroutine(result): await result
                logger.info("[gateway] Shutdown complete. All resources closed.")
                await send({"type": "lifespan.shutdown.complete"})
                return
