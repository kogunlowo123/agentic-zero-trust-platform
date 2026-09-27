"""Unit tests for policy evaluation logic.

These tests validate the OPA input construction, policy decision shaping,
and the scoring thresholds used in zero_trust.rego — all without making
real network calls.
"""

import uuid
from datetime import datetime, timezone

import pytest


# ---------------------------------------------------------------------------
# OPA input builder (mirrors services/api/src/api/routes/v1/policy.py)
# ---------------------------------------------------------------------------

def build_opa_input(
    principal_id: str = "agent-001",
    tier: str = "T1",
    svid: str = "spiffe://zero-trust.example.com/agent/test",
    token: str = "eyJtest",
    token_exp: int = 9_999_999_999,
    delegation_depth: int = 0,
    resource_id: str = "docs-api",
    resource_sensitivity: str = "MEDIUM",
    action: str = "read",
    posture_score: float = 75.0,
    context: dict | None = None,
) -> dict:
    return {
        "input": {
            "principal": {
                "id": principal_id,
                "tier": tier,
                "svid": svid,
                "token": token,
                "token_exp": token_exp,
                "delegation_depth": delegation_depth,
            },
            "resource": {
                "id": resource_id,
                "sensitivity": resource_sensitivity,
            },
            "action": action,
            "posture": {
                "score": posture_score,
                "signals": context or {},
            },
        }
    }


# ---------------------------------------------------------------------------
# Replicated OPA logic for unit-testing without OPA binary
# ---------------------------------------------------------------------------

POSTURE_THRESHOLD = {"T0": 50, "T1": 70, "T2": 90}
MAX_DEPTH = {"T0": 0, "T1": 1, "T2": 2}
SENSITIVITY_ORDINAL = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
TIER_ORDINAL = {"T0": 0, "T1": 1, "T2": 2}
TRUSTED_SVID_PREFIX = "spiffe://zero-trust.example.com/agent/"


def evaluate_policy(opa_input: dict) -> dict:
    """Python reimplementation of zero_trust.rego for unit testing."""
    inp = opa_input["input"]
    principal = inp["principal"]
    resource = inp["resource"]
    posture = inp["posture"]
    reasons: list[str] = []

    valid_svid = bool(principal.get("svid", "")) and principal["svid"].startswith(TRUSTED_SVID_PREFIX)
    if not valid_svid:
        reasons.append("INVALID_SVID")

    valid_token = bool(principal.get("token", "")) and principal.get("token_exp", 0) > 0
    if not valid_token:
        reasons.append("INVALID_OR_EXPIRED_TOKEN")

    tier = principal.get("tier", "T1")
    threshold = POSTURE_THRESHOLD.get(tier, 70)
    sufficient_posture = posture.get("score", 0) >= threshold
    if not sufficient_posture:
        reasons.append(
            f"INSUFFICIENT_POSTURE_SCORE: {posture['score']} < {threshold}"
        )

    depth = principal.get("delegation_depth", 0)
    max_d = MAX_DEPTH.get(tier, 0)
    delegation_ok = depth <= max_d
    if not delegation_ok:
        reasons.append(f"DELEGATION_DEPTH_EXCEEDED: {depth} > {max_d}")

    sens = SENSITIVITY_ORDINAL.get(resource.get("sensitivity", "LOW"), 1)
    tier_ord = TIER_ORDINAL.get(tier, 1)
    resource_ok = sens <= tier_ord + 2
    if not resource_ok:
        reasons.append(
            f"RESOURCE_SENSITIVITY_EXCEEDS_TIER: resource={resource['sensitivity']} tier={tier}"
        )

    allowed = valid_svid and valid_token and sufficient_posture and delegation_ok and resource_ok
    return {
        "allowed": allowed,
        "deny_reasons": reasons,
        "decision_id": str(uuid.uuid4()),
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestPolicyEvaluation:

    def test_allow_valid_t1_agent_medium_resource(self):
        inp = build_opa_input(tier="T1", posture_score=75.0, resource_sensitivity="MEDIUM")
        result = evaluate_policy(inp)
        assert result["allowed"] is True
        assert len(result["deny_reasons"]) == 0

    def test_allow_t2_agent_critical_resource(self):
        inp = build_opa_input(tier="T2", posture_score=95.0, resource_sensitivity="CRITICAL")
        result = evaluate_policy(inp)
        assert result["allowed"] is True

    def test_deny_low_posture_t1_agent(self):
        inp = build_opa_input(tier="T1", posture_score=45.0)
        result = evaluate_policy(inp)
        assert result["allowed"] is False
        reasons_str = " ".join(result["deny_reasons"])
        assert "INSUFFICIENT_POSTURE_SCORE" in reasons_str

    def test_deny_exactly_below_t1_threshold(self):
        inp = build_opa_input(tier="T1", posture_score=69.9)
        result = evaluate_policy(inp)
        assert result["allowed"] is False

    def test_allow_exactly_at_t1_threshold(self):
        inp = build_opa_input(tier="T1", posture_score=70.0)
        result = evaluate_policy(inp)
        assert result["allowed"] is True

    def test_deny_invalid_svid(self):
        inp = build_opa_input(svid="")
        result = evaluate_policy(inp)
        assert result["allowed"] is False
        assert "INVALID_SVID" in result["deny_reasons"]

    def test_deny_wrong_trust_domain_svid(self):
        inp = build_opa_input(svid="spiffe://attacker.com/agent/evil")
        result = evaluate_policy(inp)
        assert result["allowed"] is False
        assert "INVALID_SVID" in result["deny_reasons"]

    def test_deny_empty_token(self):
        inp = build_opa_input(token="")
        result = evaluate_policy(inp)
        assert result["allowed"] is False
        assert "INVALID_OR_EXPIRED_TOKEN" in result["deny_reasons"]

    def test_deny_t0_agent_high_resource(self):
        """T0 (ordinal 0) can access up to LOW+MEDIUM (ordinal <= 2). HIGH=3 > 0+2=2 → denied."""
        inp = build_opa_input(tier="T0", posture_score=55.0, resource_sensitivity="HIGH")
        result = evaluate_policy(inp)
        assert result["allowed"] is False
        reasons_str = " ".join(result["deny_reasons"])
        assert "RESOURCE_SENSITIVITY_EXCEEDS_TIER" in reasons_str

    def test_deny_t0_agent_critical_resource(self):
        inp = build_opa_input(tier="T0", posture_score=55.0, resource_sensitivity="CRITICAL")
        result = evaluate_policy(inp)
        assert result["allowed"] is False

    def test_deny_delegation_too_deep_t1(self):
        """T1 max_depth=1. delegation_depth=2 → denied."""
        inp = build_opa_input(tier="T1", delegation_depth=2)
        result = evaluate_policy(inp)
        assert result["allowed"] is False
        reasons_str = " ".join(result["deny_reasons"])
        assert "DELEGATION_DEPTH_EXCEEDED" in reasons_str

    def test_allow_delegation_at_max_depth_t1(self):
        inp = build_opa_input(tier="T1", delegation_depth=1)
        result = evaluate_policy(inp)
        assert result["allowed"] is True

    def test_decision_id_is_non_empty_uuid(self):
        inp = build_opa_input()
        result = evaluate_policy(inp)
        assert len(result["decision_id"]) > 0
        uuid.UUID(result["decision_id"])

    def test_denied_decision_has_reasons(self):
        inp = build_opa_input(tier="T1", posture_score=10.0)
        result = evaluate_policy(inp)
        assert not result["allowed"]
        assert len(result["deny_reasons"]) >= 1

    def test_multiple_failures_produce_multiple_reasons(self):
        inp = build_opa_input(
            tier="T1",
            svid="",
            token="",
            posture_score=10.0,
        )
        result = evaluate_policy(inp)
        assert len(result["deny_reasons"]) >= 3

    def test_t0_allow_low_resource(self):
        """T0 can access LOW sensitivity (ordinal 1 <= 0+2=2)."""
        inp = build_opa_input(tier="T0", posture_score=55.0, resource_sensitivity="LOW")
        result = evaluate_policy(inp)
        assert result["allowed"] is True

    def test_t0_allow_medium_resource(self):
        """T0 can access MEDIUM sensitivity (ordinal 2 <= 0+2=2)."""
        inp = build_opa_input(tier="T0", posture_score=55.0, resource_sensitivity="MEDIUM")
        result = evaluate_policy(inp)
        assert result["allowed"] is True


class TestOPAInputStructure:

    def test_input_has_required_top_level_keys(self):
        inp = build_opa_input()
        assert "input" in inp
        inner = inp["input"]
        for key in ["principal", "resource", "action", "posture"]:
            assert key in inner, f"Missing key: {key}"

    def test_principal_has_all_required_fields(self):
        inp = build_opa_input()
        principal = inp["input"]["principal"]
        for field in ["id", "tier", "svid", "token", "token_exp", "delegation_depth"]:
            assert field in principal, f"Missing field: {field}"

    def test_resource_has_id_and_sensitivity(self):
        inp = build_opa_input()
        resource = inp["input"]["resource"]
        assert "id" in resource
        assert "sensitivity" in resource

    def test_posture_has_score_and_signals(self):
        inp = build_opa_input()
        posture = inp["input"]["posture"]
        assert "score" in posture
        assert "signals" in posture
