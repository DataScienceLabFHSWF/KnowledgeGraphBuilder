"""Middleware for the KGBuilder API.

- ErrorHandlingMiddleware: catches unhandled exceptions and returns structured JSON
- RateLimitMiddleware: per-IP sliding window rate limiting
"""

from __future__ import annotations

import time
from collections import defaultdict

import structlog
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.types import ASGIApp

logger = structlog.get_logger(__name__)


# ------------------------------------------------------------------
# Error handling
# ------------------------------------------------------------------


class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """Catch uncaught exceptions and return a uniform JSON error body.

    Prevents raw traceback leakage to clients. All 5xx errors are
    logged with structlog for observability.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        try:
            return await call_next(request)
        except Exception as exc:
            logger.error(
                "unhandled_exception",
                method=request.method,
                path=request.url.path,
                error=str(exc),
                exc_info=True,
            )
            return JSONResponse(
                status_code=500,
                content={
                    "detail": "Internal server error",
                    "type": type(exc).__name__,
                },
            )


# ------------------------------------------------------------------
# Rate limiting
# ------------------------------------------------------------------

# Simple in-memory sliding-window rate limiter.
# Fine for a single-process dev/research API. For production use Redis.

_DEFAULT_RATE_LIMIT = 60  # requests per window
_DEFAULT_WINDOW_SECONDS = 60


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Per-IP sliding-window rate limiter.

    Args:
        app: ASGI application.
        rate_limit: Max requests per window (default 60).
        window_seconds: Window duration in seconds (default 60).
    """

    def __init__(
        self,
        app: ASGIApp,
        rate_limit: int = _DEFAULT_RATE_LIMIT,
        window_seconds: int = _DEFAULT_WINDOW_SECONDS,
    ) -> None:
        super().__init__(app)
        self.rate_limit = rate_limit
        self.window_seconds = window_seconds
        # ip → list of request timestamps
        self._requests: dict[str, list[float]] = defaultdict(list)

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # Health and docs endpoints are exempt
        if request.url.path in ("/", "/docs", "/redoc", "/openapi.json", "/api/v1/health"):
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        now = time.monotonic()
        cutoff = now - self.window_seconds

        # Prune old entries
        timestamps = self._requests[client_ip]
        self._requests[client_ip] = [t for t in timestamps if t > cutoff]

        if len(self._requests[client_ip]) >= self.rate_limit:
            logger.warning("rate_limit_exceeded", client_ip=client_ip)
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded. Try again later."},
                headers={
                    "Retry-After": str(self.window_seconds),
                    "X-RateLimit-Limit": str(self.rate_limit),
                },
            )

        self._requests[client_ip].append(now)
        response = await call_next(request)

        # Add rate-limit headers to every response
        remaining = self.rate_limit - len(self._requests[client_ip])
        response.headers["X-RateLimit-Limit"] = str(self.rate_limit)
        response.headers["X-RateLimit-Remaining"] = str(max(remaining, 0))
        return response
