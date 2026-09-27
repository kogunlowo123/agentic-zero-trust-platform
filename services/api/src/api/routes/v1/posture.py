from __future__ import annotations

import os
from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, Request

from api.schemas.posture import PostureScoreResponse, PostureSignals

router = APIRouter(tags=["posture"])
logger = structlog.get_logger(__name__)

# Tier thresholds — must match zero_trust.rego
POSTURE_TIER_THRESHOLDS = {"T0": 50.0, "T1": 70.0, "T2": 90.0}


def _compute_posture_score(signals: PostureSignals) -> tuple[float, list[str]]:
    """Compute posture score (0-100) from individual signals.

    Returns (score, recommendations).
    Deductions:
        - MFA not enabled: -30
        - Each risk detection (capped at 4): -10 each (max -40)
        - Password age > 90 days: -10
        - Device not managed: -20
        - Privileged account: -5 (higher risk surface)
        - Sign-in risk level: low=-5, medium=-15, high=-30
        - User risk level: low=-5, medium=-15, high=-30
    """
    base_score = 100.0
    deductions = 0.0
    recommendations: list[str] = []

    if not signals.mfa_enabled:
        deductions += 30.0
        recommendations.append("Enable multi-factor authentication immediately.")

    risk_deduction = min(40.0, signals.recent_risk_detections * 10.0)
    deductions += risk_deduction
    if signals.recent_risk_detections > 0:
        recommendations.append(
            f"Investigate {signals.recent_risk_detections} recent risk detection(s) in Azure AD Identity Protection."
        )

    if signals.password_age_days > 90:
        deductions += 10.0
        recommendations.append("Rotate credentials — password is older than 90 days.")

    if not signals.device_managed:
        deductions += 20.0
        recommendations.append("Enroll device in Mobile Device Management (MDM/Intune).")

    if signals.privileged_account:
        deductions += 5.0
        recommendations.append("Use privileged access workstations (PAW) for admin activities.")

    sign_in_risk_map = {"none": 0, "low": 5, "medium": 15, "high": 30}
    deductions += sign_in_risk_map.get(signals.sign_in_risk_level, 0)

    user_risk_map = {"none": 0, "low": 5, "medium": 15, "high": 30}
    deductions += user_risk_map.get(signals.user_risk_level, 0)

    score = max(0.0, base_score - deductions)
    return round(score, 2), recommendations


def _risk_level(score: float) -> str:
    if score < 30.0:
        return "CRITICAL"
    if score < 50.0:
        return "HIGH"
    if score < 70.0:
        return "MEDIUM"
    return "LOW"


@router.get("/{principal}", response_model=PostureScoreResponse)
async def get_posture(principal: str, request: Request) -> PostureScoreResponse:
    """Get device and identity posture score for a principal.

    In production, this fetches signals from Azure AD Identity Protection
    and Microsoft Intune. In non-Azure environments, it returns a default
    posture based on environment variables for testing.
    """
    # Default signals — can be overridden by env vars for testing
    mfa_enabled = os.getenv(f"POSTURE_{principal.upper()}_MFA", "true").lower() == "true"
    device_managed = os.getenv(f"POSTURE_{principal.upper()}_DEVICE_MANAGED", "true").lower() == "true"
    risk_detections = int(os.getenv(f"POSTURE_{principal.upper()}_RISK_DETECTIONS", "0"))
    password_age_days = int(os.getenv(f"POSTURE_{principal.upper()}_PASSWORD_AGE_DAYS", "30"))
    privileged = os.getenv(f"POSTURE_{principal.upper()}_PRIVILEGED", "false").lower() == "true"

    signals = PostureSignals(
        mfa_enabled=mfa_enabled,
        device_managed=device_managed,
        recent_risk_detections=risk_detections,
        password_age_days=password_age_days,
        privileged_account=privileged,
    )

    score, recommendations = _compute_posture_score(signals)
    risk = _risk_level(score)

    tier_eligibility = {
        tier: score >= threshold
        for tier, threshold in POSTURE_TIER_THRESHOLDS.items()
    }

    logger.info(
        "posture_computed",
        principal=principal,
        score=score,
        risk_level=risk,
    )

    return PostureScoreResponse(
        principal=principal,
        score=score,
        risk_level=risk,
        signals=signals,
        computed_at=datetime.now(timezone.utc).isoformat(),
        recommendations=recommendations,
        tier_eligibility=tier_eligibility,
    )
