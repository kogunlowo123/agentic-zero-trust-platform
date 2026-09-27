from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class PostureSignals(BaseModel):
    """Device and identity posture signals."""

    mfa_enabled: bool = Field(default=False, description="Whether MFA is enforced for this identity.")
    device_managed: bool = Field(default=False, description="Whether the device is enrolled in MDM.")
    recent_risk_detections: int = Field(
        default=0,
        ge=0,
        description="Number of Azure AD Identity Protection risk detections in the last 24h.",
    )
    password_age_days: int = Field(
        default=90,
        ge=0,
        description="Age of the current password or credential in days.",
    )
    privileged_account: bool = Field(
        default=False,
        description="Whether this account has privileged/admin roles.",
    )
    sign_in_risk_level: Literal["none", "low", "medium", "high"] = Field(
        default="none",
        description="Azure AD sign-in risk level.",
    )
    user_risk_level: Literal["none", "low", "medium", "high"] = Field(
        default="none",
        description="Azure AD user risk level.",
    )


class PostureScoreResponse(BaseModel):
    """Response body for GET /api/v1/posture/{principal}."""

    principal: str = Field(..., description="The principal whose posture was assessed.")
    score: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Posture score from 0 (worst) to 100 (best).",
    )
    risk_level: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"] = Field(
        ...,
        description="Risk level derived from the posture score.",
    )
    signals: PostureSignals = Field(..., description="Individual posture signals that contributed to the score.")
    computed_at: str = Field(..., description="ISO-8601 UTC timestamp when the score was computed.")
    recommendations: list[str] = Field(
        default_factory=list,
        description="Actionable recommendations to improve posture score.",
    )
    tier_eligibility: dict[str, bool] = Field(
        default_factory=dict,
        description="Whether the current score meets each tier's threshold. e.g. {'T0': True, 'T1': False, 'T2': False}",
    )
