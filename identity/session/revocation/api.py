"""Token and Session Revocation API.

Provides endpoints to revoke JWT tokens (by JTI) and check revocation status.
Revoked token JTIs are stored in Redis with TTL equal to the token's remaining
validity period.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

import structlog
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

logger = structlog.get_logger(__name__)
app = FastAPI(title="Revocation API", version="0.1.0")

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
REVOCATION_PREFIX = "revoked:jti:"


def _get_redis():
    try:
        import redis

        return redis.from_url(REDIS_URL, decode_responses=True)
    except Exception as exc:
        logger.error("redis_connection_failed", error=str(exc))
        return None


class RevokeRequest(BaseModel):
    jti: str
    reason: str = "manual_revocation"
    expires_at: str | None = None  # ISO-8601 UTC; if None, TTL=86400


@app.post("/revoke", status_code=201)
async def revoke_token(body: RevokeRequest) -> dict:
    """Add a token JTI to the revocation list."""
    r = _get_redis()
    if r is None:
        raise HTTPException(status_code=503, detail="Revocation store unavailable")

    ttl = 86400  # default 24h
    if body.expires_at:
        try:
            expires = datetime.fromisoformat(body.expires_at)
            now = datetime.now(timezone.utc)
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=timezone.utc)
            remaining = int((expires - now).total_seconds())
            ttl = max(60, remaining)
        except ValueError:
            pass

    key = f"{REVOCATION_PREFIX}{body.jti}"
    r.setex(key, ttl, body.reason)

    logger.info("token_revoked", jti=body.jti, reason=body.reason, ttl_seconds=ttl)
    return {"jti": body.jti, "revoked": True, "reason": body.reason, "ttl_seconds": ttl}


@app.get("/check/{jti}")
async def check_revocation(jti: str) -> dict:
    """Check whether a token JTI is in the revocation list."""
    r = _get_redis()
    if r is None:
        raise HTTPException(status_code=503, detail="Revocation store unavailable")

    key = f"{REVOCATION_PREFIX}{jti}"
    reason = r.get(key)
    ttl = r.ttl(key)

    return {
        "jti": jti,
        "revoked": reason is not None,
        "reason": reason,
        "ttl_seconds": ttl if ttl > 0 else None,
    }


@app.delete("/revoke/{jti}")
async def remove_revocation(jti: str) -> dict:
    """Remove a JTI from the revocation list (admin operation)."""
    r = _get_redis()
    if r is None:
        raise HTTPException(status_code=503, detail="Revocation store unavailable")

    key = f"{REVOCATION_PREFIX}{jti}"
    deleted = r.delete(key)
    logger.info("revocation_removed", jti=jti, was_present=bool(deleted))
    return {"jti": jti, "removed": bool(deleted)}


@app.get("/health")
async def health() -> dict:
    r = _get_redis()
    redis_ok = False
    if r is not None:
        try:
            r.ping()
            redis_ok = True
        except Exception:
            pass
    return {"status": "ok" if redis_ok else "degraded", "redis": redis_ok}
