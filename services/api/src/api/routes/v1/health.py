from __future__ import annotations

import os
from datetime import datetime, timezone

import httpx
import structlog
from fastapi import APIRouter
from fastapi.responses import JSONResponse

logger = structlog.get_logger(__name__)
router = APIRouter(tags=["health"])

OPA_URL = os.getenv("OPA_URL", "http://opa:8181")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
VERSION = "0.1.0"


@router.get("/health")
async def health() -> dict:
    """Liveness probe — always returns 200 if the process is alive."""
    return {
        "status": "ok",
        "version": VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/readiness")
async def readiness():
    """Readiness probe — checks all upstream dependencies.

    Returns 200 if all dependencies are reachable, 503 otherwise.
    """
    checks: dict[str, str] = {}
    failed: list[str] = []

    # Check OPA
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{OPA_URL}/health")
            if resp.status_code == 200:
                checks["opa"] = "ok"
            else:
                checks["opa"] = f"unhealthy ({resp.status_code})"
                failed.append("opa")
    except Exception as exc:
        checks["opa"] = f"unreachable ({exc})"
        failed.append("opa")

    # Check Redis
    try:
        import redis

        r = redis.from_url(REDIS_URL, socket_connect_timeout=2)
        r.ping()
        checks["redis"] = "ok"
    except Exception as exc:
        checks["redis"] = f"unreachable ({exc})"
        failed.append("redis")

    status_code = 503 if failed else 200
    body = {
        "status": "degraded" if failed else "ok",
        "checks": checks,
        "failed_checks": failed,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    if failed:
        logger.warning("readiness_check_failed", failed=failed, checks=checks)

    return JSONResponse(content=body, status_code=status_code)
