from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timedelta, timezone

import structlog
from fastapi import APIRouter, HTTPException, Request

from api.schemas.access import AccessRequestCreate, AccessRequestResponse, AccessRequestStatus

router = APIRouter(tags=["access"])
logger = structlog.get_logger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
ACCESS_REQUEST_TTL = 86400  # 24 hours


def _get_redis():
    try:
        import redis

        return redis.from_url(REDIS_URL, decode_responses=True)
    except Exception as exc:
        logger.warning("redis_unavailable", error=str(exc))
        return None


@router.post("/request", response_model=AccessRequestResponse, status_code=201)
async def submit_access_request(
    body: AccessRequestCreate,
    request: Request,
) -> AccessRequestResponse:
    """Submit a JIT access request for approval.

    Creates a pending access request stored in Redis and publishes to the
    Service Bus access_requests queue for the approval workflow.
    """
    principal: str = getattr(request.state, "principal", "unknown")
    request_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=body.duration_minutes)

    record = {
        "request_id": request_id,
        "principal": principal,
        "resource": body.resource,
        "action": body.action,
        "justification": body.justification,
        "duration_minutes": body.duration_minutes,
        "status": "pending",
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
        "expires_at": expires_at.isoformat(),
        "approved_by": None,
        "denied_reason": None,
    }

    r = _get_redis()
    if r is not None:
        try:
            r.setex(f"access_request:{request_id}", ACCESS_REQUEST_TTL, json.dumps(record))
        except Exception as exc:
            logger.error("failed_to_store_access_request", error=str(exc))
            raise HTTPException(status_code=503, detail="Storage unavailable")

    # Publish to Service Bus
    sb_conn = os.getenv("AZURE_SERVICE_BUS_CONNECTION_STRING", "")
    if sb_conn:
        try:
            from azure.servicebus import ServiceBusMessage
            from azure.servicebus.aio import ServiceBusClient

            import asyncio

            async def _send():
                async with ServiceBusClient.from_connection_string(sb_conn) as client:
                    async with client.get_queue_sender("access-requests") as sender:
                        await sender.send_messages(ServiceBusMessage(json.dumps(record)))

            asyncio.create_task(_send())
        except Exception as exc:
            logger.warning("failed_to_publish_access_request", error=str(exc))

    logger.info(
        "access_request_submitted",
        request_id=request_id,
        principal=principal,
        resource=body.resource,
        action=body.action,
    )

    return AccessRequestResponse(
        request_id=request_id,
        principal=principal,
        resource=body.resource,
        action=body.action,
        status="pending",
        created_at=now.isoformat(),
        expires_at=None,
    )


@router.get("/{request_id}/status", response_model=AccessRequestStatus)
async def get_access_request_status(request_id: str) -> AccessRequestStatus:
    """Check the approval status of a JIT access request."""
    r = _get_redis()
    if r is None:
        raise HTTPException(status_code=503, detail="Storage unavailable")

    raw = r.get(f"access_request:{request_id}")
    if raw is None:
        raise HTTPException(status_code=404, detail=f"Access request {request_id} not found")

    try:
        record = json.loads(raw)
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Corrupted access request record")

    return AccessRequestStatus(
        request_id=record["request_id"],
        status=record["status"],
        principal=record["principal"],
        resource=record["resource"],
        action=record["action"],
        approved_by=record.get("approved_by"),
        denied_reason=record.get("denied_reason"),
        created_at=record["created_at"],
        updated_at=record.get("updated_at", record["created_at"]),
        expires_at=record.get("expires_at"),
    )
