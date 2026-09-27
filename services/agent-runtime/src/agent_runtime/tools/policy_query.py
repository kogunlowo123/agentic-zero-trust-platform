import os
import uuid
from datetime import datetime, timezone

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from agent_runtime.tools.base import BaseTool

_OPA_URL = os.environ.get("OPA_URL", "http://opa:8181")


class PolicyQueryTool(BaseTool):
    """Query the OPA policy engine for fine-grained authorization decisions."""

    @property
    def name(self) -> str:
        return "policy_query"

    @property
    def description(self) -> str:
        return (
            "Query the OPA policy engine to determine whether a principal is "
            "allowed to perform an action on a resource under zero-trust policies."
        )

    @property
    def schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "principal_id": {
                    "type": "string",
                    "description": "The identity of the requesting principal.",
                },
                "principal_tier": {
                    "type": "string",
                    "enum": ["T0", "T1", "T2"],
                    "description": "The trust tier of the principal.",
                },
                "resource_id": {
                    "type": "string",
                    "description": "The resource being accessed.",
                },
                "resource_sensitivity": {
                    "type": "string",
                    "description": "Sensitivity classification of the resource.",
                },
                "action": {
                    "type": "string",
                    "description": "The action being requested (e.g. 'read', 'write').",
                },
                "posture_score": {
                    "type": "number",
                    "description": "Current posture score of the principal (0-100).",
                },
                "svid": {
                    "type": "string",
                    "description": "Optional SPIFFE SVID for workload identity.",
                },
                "token": {
                    "type": "string",
                    "description": "Optional bearer token for authenticated callers.",
                },
            },
            "required": [
                "principal_id",
                "principal_tier",
                "resource_id",
                "resource_sensitivity",
                "action",
                "posture_score",
            ],
        }

    async def call(
        self,
        principal_id: str,
        principal_tier: str,
        resource_id: str,
        resource_sensitivity: str,
        action: str,
        posture_score: float,
        svid: str | None = None,
        token: str | None = None,
    ) -> dict:
        return await policy_query_tool(
            principal_id=principal_id,
            principal_tier=principal_tier,
            resource_id=resource_id,
            resource_sensitivity=resource_sensitivity,
            action=action,
            posture_score=posture_score,
            svid=svid,
            token=token,
        )


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    reraise=True,
)
async def policy_query_tool(
    principal_id: str,
    principal_tier: str,
    resource_id: str,
    resource_sensitivity: str,
    action: str,
    posture_score: float,
    svid: str | None = None,
    token: str | None = None,
) -> dict:
    """Query OPA for an allow/deny decision.

    Sends a POST to ``OPA_URL/v1/data/zerotrust/allow`` with a structured
    input payload and returns a normalised PolicyDecision dict.

    Args:
        principal_id: The identity of the requesting principal.
        principal_tier: Trust tier ('T0', 'T1', 'T2').
        resource_id: The resource being accessed.
        resource_sensitivity: Sensitivity label of the resource.
        action: The requested action.
        posture_score: Current posture score (0-100).
        svid: Optional SPIFFE SVID for workload identity verification.
        token: Optional bearer token forwarded to OPA as a header.

    Returns:
        A dict matching the PolicyDecision contract:
            - allowed (bool)
            - reasons (list[str])
            - principal (str)
            - timestamp (str, ISO 8601)
            - decision_id (str)

    Raises:
        RuntimeError: On HTTP error or unreachable OPA instance.
    """
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    opa_input: dict = {
        "input": {
            "principal": {
                "id": principal_id,
                "tier": principal_tier,
            },
            "resource": {
                "id": resource_id,
                "sensitivity": resource_sensitivity,
            },
            "action": action,
            "posture_score": posture_score,
        }
    }
    if svid:
        opa_input["input"]["svid"] = svid

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.post(
                f"{_OPA_URL}/v1/data/zerotrust/allow",
                json=opa_input,
                headers=headers,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(
                f"OPA policy query failed with status {exc.response.status_code}: "
                f"{exc.response.text}"
            ) from exc
        except httpx.RequestError as exc:
            raise RuntimeError(
                f"Failed to reach OPA at {_OPA_URL}: {exc}"
            ) from exc

        body = response.json()

    # OPA wraps its result in {"result": ...}
    result = body.get("result", {})
    allowed: bool = bool(result.get("allow", False))
    reasons: list[str] = result.get("reasons", [])
    if not reasons:
        reasons = ["allow" if allowed else "deny — no matching allow rule"]

    return {
        "allowed": allowed,
        "reasons": reasons,
        "principal": principal_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "decision_id": str(uuid.uuid4()),
    }
