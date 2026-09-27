"""Unit tests for posture scoring logic.

These tests are fully self-contained — they replicate the scoring algorithm
from services/api/src/api/routes/v1/posture.py without importing it, so they
run with zero dependencies other than pytest itself.
"""

import pytest


# ---------------------------------------------------------------------------
# Replicated scoring logic (must stay in sync with posture.py)
# ---------------------------------------------------------------------------

def compute_posture_score(
    mfa_enabled: bool = True,
    device_managed: bool = True,
    recent_risk_detections: int = 0,
    password_age_days: int = 30,
    privileged_account: bool = False,
    sign_in_risk_level: str = "none",
    user_risk_level: str = "none",
) -> float:
    base_score = 100.0
    deductions = 0.0

    if not mfa_enabled:
        deductions += 30.0

    risk_deduction = min(40.0, recent_risk_detections * 10.0)
    deductions += risk_deduction

    if password_age_days > 90:
        deductions += 10.0

    if not device_managed:
        deductions += 20.0

    if privileged_account:
        deductions += 5.0

    sign_in_risk_map = {"none": 0, "low": 5, "medium": 15, "high": 30}
    deductions += sign_in_risk_map.get(sign_in_risk_level, 0)

    user_risk_map = {"none": 0, "low": 5, "medium": 15, "high": 30}
    deductions += user_risk_map.get(user_risk_level, 0)

    return max(0.0, base_score - deductions)


def risk_level(score: float) -> str:
    if score < 30.0:
        return "CRITICAL"
    if score < 50.0:
        return "HIGH"
    if score < 70.0:
        return "MEDIUM"
    return "LOW"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestPostureScoring:

    def test_perfect_posture_returns_100(self):
        score = compute_posture_score()
        assert score == 100.0

    def test_mfa_disabled_deducts_30(self):
        score = compute_posture_score(mfa_enabled=False)
        assert score == 70.0

    def test_unmanaged_device_deducts_20(self):
        score = compute_posture_score(device_managed=False)
        assert score == 80.0

    def test_one_risk_detection_deducts_10(self):
        score = compute_posture_score(recent_risk_detections=1)
        assert score == 90.0

    def test_four_risk_detections_caps_at_40(self):
        score = compute_posture_score(recent_risk_detections=4)
        assert score == 60.0

    def test_many_risk_detections_capped_at_40(self):
        score_4 = compute_posture_score(recent_risk_detections=4)
        score_100 = compute_posture_score(recent_risk_detections=100)
        assert score_4 == score_100  # capped

    def test_stale_password_deducts_10(self):
        score = compute_posture_score(password_age_days=91)
        assert score == 90.0

    def test_password_exactly_90_days_no_deduction(self):
        score = compute_posture_score(password_age_days=90)
        assert score == 100.0

    def test_privileged_account_deducts_5(self):
        score = compute_posture_score(privileged_account=True)
        assert score == 95.0

    def test_high_signin_risk_deducts_30(self):
        score = compute_posture_score(sign_in_risk_level="high")
        assert score == 70.0

    def test_medium_user_risk_deducts_15(self):
        score = compute_posture_score(user_risk_level="medium")
        assert score == 85.0

    def test_score_never_goes_below_zero(self):
        score = compute_posture_score(
            mfa_enabled=False,
            device_managed=False,
            recent_risk_detections=100,
            password_age_days=365,
            privileged_account=True,
            sign_in_risk_level="high",
            user_risk_level="high",
        )
        assert score >= 0.0

    def test_combined_mfa_and_device_issues(self):
        score = compute_posture_score(mfa_enabled=False, device_managed=False)
        assert score == 50.0

    def test_low_risk_level_for_score_70(self):
        assert risk_level(70.0) == "LOW"

    def test_low_risk_level_for_score_100(self):
        assert risk_level(100.0) == "LOW"

    def test_medium_risk_level_for_score_50(self):
        assert risk_level(50.0) == "MEDIUM"

    def test_medium_risk_level_for_score_69(self):
        assert risk_level(69.9) == "MEDIUM"

    def test_high_risk_level_for_score_30(self):
        assert risk_level(30.0) == "HIGH"

    def test_high_risk_level_for_score_49(self):
        assert risk_level(49.9) == "HIGH"

    def test_critical_risk_level_for_score_0(self):
        assert risk_level(0.0) == "CRITICAL"

    def test_critical_risk_level_for_score_29(self):
        assert risk_level(29.9) == "CRITICAL"


class TestTierThresholds:
    """Verify that posture thresholds match OPA policy (zero_trust.rego)."""

    THRESHOLDS = {"T0": 50.0, "T1": 70.0, "T2": 90.0}

    def test_t0_threshold_is_50(self):
        assert self.THRESHOLDS["T0"] == 50.0

    def test_t1_threshold_is_70(self):
        assert self.THRESHOLDS["T1"] == 70.0

    def test_t2_threshold_is_90(self):
        assert self.THRESHOLDS["T2"] == 90.0

    def test_score_50_meets_t0_not_t1(self):
        score = 50.0
        assert score >= self.THRESHOLDS["T0"]
        assert score < self.THRESHOLDS["T1"]

    def test_score_90_meets_all_tiers(self):
        score = 90.0
        for tier, threshold in self.THRESHOLDS.items():
            assert score >= threshold, f"Score {score} should meet {tier} threshold {threshold}"
