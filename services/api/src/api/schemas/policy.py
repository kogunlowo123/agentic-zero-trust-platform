from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class PolicyEvaluateRequest(BaseModel):
    """Request body for POST /api/v1/policy/evaluate."""

    resource_id: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Identifier of the resource being accessed.",
        examples=["policy-corpus", "secrets/db-prod", "agent-registry"],
    )
    resource_sensitivity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"] = Field(
        default="MEDIUM",
        description="Sensitivity classification of the target resource.",
    )
    action: Literal["read", "write", "execute", "admin", "list"] = Field(
        default="read",
        description="The action the principal wants to perform.",
    )
    context: dict = Field(
        default_factory=dict,
        description="Additional context forwarded to the OPA input as posture.signals.",
    )


class PolicyEvaluateResponse(BaseModel):
    """Response body for POST /api/v1/policy/evaluate."""

    allowed: bool = Field(..., description="Whether the policy engine granted access.")
    reasons: list[str] = Field(
        default_factory=list,
        description="Reasons for the decision — populated on deny.",
    )
    principal: str = Field(..., description="The authenticated principal that made the request.")
    decision_id: str = Field(..., description="Unique identifier for this policy decision.")
    timestamp: str = Field(..., description="ISO-8601 UTC timestamp of the decision.")
    policy_version: str = Field(default="1.0", description="Version of the policy evaluated.")
