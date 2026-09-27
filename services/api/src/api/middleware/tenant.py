from __future__ import annotations

import os

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = structlog.get_logger(__name__)

SKIP_PATHS: frozenset[str] = frozenset(
    {"/api/v1/health", "/api/v1/readiness", "/docs", "/openapi.json", "/redoc"}
)

# Comma-separated list of allowed tenant IDs from env
_ALLOWED_TENANTS_RAW = os.getenv("ALLOWED_TENANT_IDS", "")
ALLOWED_TENANTS: frozenset[str] = (
    frozenset(t.strip() for t in _ALLOWED_TENANTS_RAW.split(",") if t.strip())
    if _ALLOWED_TENANTS_RAW
    else frozenset()  # empty = allow all (single-tenant mode)
)


class TenantMiddleware(BaseHTTPMiddleware):
    """Extract and validate X-Tenant-ID header.

    In single-tenant mode (ALLOWED_TENANT_IDS not set), the tenant_id is
    taken from the header but not validated against a whitelist.
    """

    async def dispatch(self, request: Request, call_next):
        if request.url.path in SKIP_PATHS:
            return await call_next(request)

        tenant_id = request.headers.get("X-Tenant-ID", "default")

        if ALLOWED_TENANTS and tenant_id not in ALLOWED_TENANTS:
            logger.warning("unknown_tenant", tenant_id=tenant_id, path=request.url.path)
            return JSONResponse(
                {"detail": f"Unknown tenant: {tenant_id}"},
                status_code=403,
            )

        request.state.tenant_id = tenant_id
        return await call_next(request)
