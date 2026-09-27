from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class AccessRequestCreate(BaseModel):
    """Request body for POST /api/v1/access/request."""

    resource: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="The resource requiring just-in-time access.",
        examples=["secrets/prod-db", "cluster/prod-admin"],
    )
    action: Literal["read", "write", "execute", "admin", "list"] = Field(
        ...,
        description="The action requested on the resource.",
    )
    justification: str = Field(
        ...,
        min_length=10,
        max_length=1000,
        description="Business justification for why this access is needed.",
    )
    duration_minutes: int = Field(
        ...,
        ge=1,
        le=480,
        description="Requested access duration in minutes. Maximum 480 (8 hours).",
    )


class AccessRequestResponse(BaseModel):
    """Response body for POST /api/v1/access/request."""

    request_id: str = Field(..., description="Unique identifier for the access request.")
    principal: str = Field(..., description="The principal that submitted the request.")
    resource: str
    action: str
    status: Literal["pending", "approved", "denied"] = Field(
        default="pending",
        description="Current status of the access request.",
    )
    created_at: str = Field(..., description="ISO-8601 UTC creation timestamp.")
    expires_at: str | None = Field(
        default=None,
        description="ISO-8601 UTC expiry timestamp, set when approved.",
    )


class AccessRequestStatus(BaseModel):
    """Response body for GET /api/v1/access/{id}/status."""

    request_id: str
    status: Literal["pending", "approved", "denied"]
    principal: str
    resource: str
    action: str
    approved_by: str | None = None
    denied_reason: str | None = None
    created_at: str
    updated_at: str
    expires_at: str | None = None
