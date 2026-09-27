from __future__ import annotations

import os

import jwt
import structlog
from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

logger = structlog.get_logger(__name__)

JWT_SECRET = os.getenv("JWT_SECRET_KEY", "dev-secret-change-in-production")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")

# Paths that do not require authentication
SKIP_PATHS: frozenset[str] = frozenset(
    {
        "/api/v1/health",
        "/api/v1/readiness",
        "/docs",
        "/openapi.json",
        "/redoc",
    }
)


class AuthMiddleware(BaseHTTPMiddleware):
    """JWT Bearer token authentication middleware.

    Validates the Authorization header, decodes the JWT, and attaches
    principal / tier / posture claims to request.state for downstream use.
    """

    async def dispatch(self, request: Request, call_next):
        if request.url.path in SKIP_PATHS:
            return await call_next(request)

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return JSONResponse(
                {"detail": "Missing or invalid Authorization header. Expected: Bearer <token>"},
                status_code=401,
                headers={"WWW-Authenticate": "Bearer"},
            )

        token = auth_header[7:]
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        except jwt.ExpiredSignatureError:
            return JSONResponse(
                {"detail": "Token has expired"},
                status_code=401,
                headers={"WWW-Authenticate": "Bearer"},
            )
        except jwt.InvalidTokenError as exc:
            logger.warning("invalid_jwt", error=str(exc))
            return JSONResponse(
                {"detail": f"Invalid token: {exc}"},
                status_code=401,
                headers={"WWW-Authenticate": "Bearer"},
            )

        request.state.principal = payload.get("sub", "unknown")
        request.state.tier = payload.get("tier", "T1")
        request.state.token = token
        request.state.token_exp = int(payload.get("exp", 9_999_999_999))
        request.state.svid = payload.get("svid", "")
        request.state.posture_score = float(payload.get("posture_score", 75.0))
        request.state.jti = payload.get("jti", "")

        logger.debug(
            "request_authenticated",
            principal=request.state.principal,
            tier=request.state.tier,
            path=request.url.path,
        )

        return await call_next(request)


async def get_current_principal(request: Request) -> str:
    """FastAPI dependency: extract the authenticated principal from request state."""
    principal = getattr(request.state, "principal", None)
    if principal is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return principal
