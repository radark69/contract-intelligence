"""Rate limiting middleware (simple in-memory, per-IP)."""

import time
from collections import defaultdict
from dataclasses import dataclass

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# Default: 100 requests per minute per IP
DEFAULT_LIMIT = 100
DEFAULT_WINDOW = 60  # seconds

# Stricter limits for auth endpoints
AUTH_LIMIT = 10
AUTH_WINDOW = 60

# Upload endpoints
UPLOAD_LIMIT = 5
UPLOAD_WINDOW = 60


@dataclass
class RateLimitConfig:
    limit: int
    window: int


# Path-specific limits (prefix matching)
PATH_LIMITS = {
    "/api/v1/auth/login": RateLimitConfig(AUTH_LIMIT, AUTH_WINDOW),
    "/api/v1/auth/register": RateLimitConfig(AUTH_LIMIT, AUTH_WINDOW),
    "/api/v1/auth/refresh": RateLimitConfig(AUTH_LIMIT, AUTH_WINDOW),
    "/api/v1/documents/upload": RateLimitConfig(UPLOAD_LIMIT, UPLOAD_WINDOW),
    "/api/v1/documents": RateLimitConfig(DEFAULT_LIMIT, DEFAULT_WINDOW),
}


class RateLimiter:
    def __init__(self):
        self.requests: dict[str, list[float]] = defaultdict(list)

    def is_allowed(self, key: str, limit: int, window: int) -> tuple[bool, int]:
        now = time.time()
        window_start = now - window
        # Clean old entries
        self.requests[key] = [t for t in self.requests[key] if t > window_start]
        if len(self.requests[key]) >= limit:
            return False, int(window - (now - self.requests[key][0]))
        self.requests[key].append(now)
        return True, 0


rate_limiter = RateLimiter()


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for health checks
        if request.url.path in ("/health", "/docs", "/redoc", "/openapi.json"):
            return await call_next(request)

        # Determine limit config
        config = RateLimitConfig(DEFAULT_LIMIT, DEFAULT_WINDOW)
        for path, c in PATH_LIMITS.items():
            if request.url.path.startswith(path):
                config = c
                break

        # Client identifier (IP + User-Agent for better granularity)
        client_ip = request.client.host if request.client else "unknown"
        key = f"{client_ip}:{request.url.path}"

        allowed, retry_after = rate_limiter.is_allowed(key, config.limit, config.window)
        if not allowed:
            return Response(
                content=f"Rate limit exceeded. Try again in {retry_after} seconds.",
                status_code=429,
                headers={"Retry-After": str(retry_after)},
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(config.limit)
        response.headers["X-RateLimit-Remaining"] = str(
            max(0, config.limit - len(rate_limiter.requests.get(key, [])))
        )
        return response


def rate_limit_middleware(app):
    return RateLimitMiddleware(app)