from __future__ import annotations

import os
import time
from typing import Optional

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = structlog.get_logger(__name__)

SKIP_PATHS: frozenset[str] = frozenset({"/api/v1/health", "/api/v1/readiness"})


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Sliding window rate limiter using Redis.

    Falls back to allowing all requests if Redis is unavailable so that a
    Redis outage does not take down the API entirely.
    """

    def __init__(self, app, requests_per_minute: int = 60):
        super().__init__(app)
        self.limit = requests_per_minute
        self._redis: Optional[object] = None

    def _get_redis(self):
        if self._redis is None:
            try:
                import redis

                redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
                self._redis = redis.from_url(redis_url, decode_responses=True)
            except Exception as exc:
                logger.warning("redis_unavailable_for_ratelimit", error=str(exc))
        return self._redis

    async def dispatch(self, request: Request, call_next):
        if request.url.path in SKIP_PATHS:
            return await call_next(request)

        principal = getattr(request.state, "principal", request.client.host if request.client else "anonymous")
        window = int(time.time()) // 60  # 1-minute sliding window bucket
        key = f"ratelimit:{principal}:{window}"

        r = self._get_redis()
        if r is not None:
            try:
                current = r.incr(key)
                if current == 1:
                    r.expire(key, 120)  # expire after 2 windows for safety
                if current > self.limit:
                    retry_after = 60 - (int(time.time()) % 60)
                    logger.warning(
                        "rate_limit_exceeded",
                        principal=principal,
                        count=current,
                        limit=self.limit,
                    )
                    return JSONResponse(
                        {
                            "detail": f"Rate limit exceeded. {self.limit} requests per minute allowed.",
                            "retry_after": retry_after,
                        },
                        status_code=429,
                        headers={"Retry-After": str(retry_after)},
                    )
            except Exception as exc:
                logger.warning("rate_limit_check_failed", error=str(exc))
                # Fail open: allow request if Redis check fails

        return await call_next(request)
