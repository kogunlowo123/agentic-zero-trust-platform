from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone

import httpx
import structlog
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request

from api.schemas.policy import PolicyEvaluateRequest, PolicyEvaluateResponse

router = APIRouter(tags=["policy"])
logger = structlog.get_logger(__name__)

OPA_URL = os.getenv("OPA_URL", "http://opa:8181")


async def _emit_violation_event(
    principal: str,
    resource: str,
    action: str,
    reasons: list[str],
    decision_id: str,
) -> None:
    """Publish a CloudEvent to the Service Bus policy-violations queue."""
    event = {
        "specversion": "1.0",
        "type": "policy.violation",
        "source": "agentic-zero-trust/policy-enforcer",
        "id": decision_id,
        "time": datetime.now(timezone.utc).isoformat(),
        "datacontenttype": "application/json",
        "data": {
            "principal": principal,
            "resource": resource,
            "action": action,
            "reasons": reasons,
        },
    }
    sb_conn = os.getenv("AZURE_SERVICE_BUS_CONNECTION_STRING", "")
    if not sb_conn:
        logger.debug("service_bus_not_configured_skipping_event")
        return
    try:
        from azure.servicebus import ServiceBusMessage
        from azure.servicebus.aio import ServiceBusClient

        async with ServiceBusClient.from_connection_string(sb_conn) as client:
            async with client.get_queue_sender("policy-violations") as sender:
                await sender.send_messages(ServiceBusMessage(json.dumps(event)))
    except Exception as exc:
        logger.warning("failed_to_publish_violation_event", error=str(exc), decision_id=decision_id)


@router.post("/evaluate", response_model=PolicyEvaluateResponse)
async def evaluate_policy(
    request_body: PolicyEvaluateRequest,
    background_tasks: BackgroundTasks,
    request: Request,
) -> PolicyEvaluateResponse:
    """Evaluate a zero-trust policy decision via OPA.

    Extracts the authenticated principal from JWT claims, builds the OPA input,
    calls OPA /v1/data/zerotrust, and returns a PolicyDecision.
    On denial, asynchronously publishes a policy.violation CloudEvent.
    """
    principal: str = getattr(request.state, "principal", "unknown")
    tier: str = getattr(request.state, "tier", "T1")
    svid: str = getattr(request.state, "svid", "")
    token: str = getattr(request.state, "token", "")
    token_exp: int = int(getattr(request.state, "token_exp", 9_999_999_999))
    posture_score: float = float(getattr(request.state, "posture_score", 75.0))

    decision_id = str(uuid.uuid4())

    opa_input = {
        "input": {
            "principal": {
                "id": principal,
                "tier": tier,
                "svid": svid,
                "token": token,
                "token_exp": token_exp,
                "delegation_depth": 0,
            },
            "resource": {
                "id": request_body.resource_id,
                "sensitivity": request_body.resource_sensitivity,
            },
            "action": request_body.action,
            "posture": {
                "score": posture_score,
                "signals": request_body.context,
            },
        }
    }

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(f"{OPA_URL}/v1/data/zerotrust", json=opa_input)
            resp.raise_for_status()
            opa_result = resp.json().get("result", {})
    except httpx.TimeoutException:
        logger.error("opa_timeout", opa_url=OPA_URL)
        raise HTTPException(status_code=503, detail="Policy engine timed out")
    except httpx.HTTPStatusError as exc:
        logger.error("opa_http_error", status=exc.response.status_code)
        raise HTTPException(status_code=503, detail=f"Policy engine returned {exc.response.status_code}")
    except httpx.RequestError as exc:
        logger.error("opa_request_error", error=str(exc))
        raise HTTPException(status_code=503, detail="Policy engine unreachable")

    allowed: bool = bool(opa_result.get("allow", False))
    # deny_reasons is a set in OPA; comes back as list or dict
    raw_reasons = opa_result.get("deny_reasons", [])
    reasons: list[str] = list(raw_reasons) if isinstance(raw_reasons, (list, set)) else []

    logger.info(
        "policy_evaluated",
        principal=principal,
        tier=tier,
        resource=request_body.resource_id,
        action=request_body.action,
        allowed=allowed,
        decision_id=decision_id,
    )

    if not allowed:
        background_tasks.add_task(
            _emit_violation_event,
            principal,
            request_body.resource_id,
            request_body.action,
            reasons,
            decision_id,
        )

    return PolicyEvaluateResponse(
        allowed=allowed,
        reasons=reasons,
        principal=principal,
        decision_id=decision_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
