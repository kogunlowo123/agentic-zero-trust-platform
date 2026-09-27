"""Unit tests for JIT access request logic.

All tests are self-contained — no external dependencies.
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest


# ---------------------------------------------------------------------------
# Replicated JIT access logic
# ---------------------------------------------------------------------------

VALID_ACTIONS = {"read", "write", "execute", "admin", "list"}


def validate_access_request(
    principal: Any,
    resource: Any,
    action: Any,
    justification: Any,
    duration_minutes: Any,
) -> list[str]:
    """Returns a list of validation error strings."""
    errors: list[str] = []

    if not principal or not isinstance(principal, str) or not principal.strip():
        errors.append("principal must be a non-empty string")

    if not resource or not isinstance(resource, str) or not resource.strip():
        errors.append("resource must be a non-empty string")

    if not action or action not in VALID_ACTIONS:
        errors.append(f"action must be one of {sorted(VALID_ACTIONS)}")

    if not justification or not isinstance(justification, str) or len(justification.strip()) < 10:
        errors.append("justification must be at least 10 characters")

    if not isinstance(duration_minutes, int) or not (1 <= duration_minutes <= 480):
        errors.append("duration_minutes must be an integer between 1 and 480 inclusive")

    return errors


def create_access_request(
    principal: str,
    resource: str,
    action: str,
    justification: str,
    duration_minutes: int,
) -> dict:
    errors = validate_access_request(principal, resource, action, justification, duration_minutes)
    if errors:
        raise ValueError("; ".join(errors))

    now = datetime.now(timezone.utc)
    return {
        "request_id": str(uuid.uuid4()),
        "principal": principal,
        "resource": resource,
        "action": action,
        "justification": justification,
        "duration_minutes": duration_minutes,
        "status": "pending",
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
        "expires_at": (now + timedelta(minutes=duration_minutes)).isoformat(),
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestJITAccessValidation:

    def test_valid_request_succeeds(self):
        req = create_access_request(
            "agent-001", "secrets/db-prod", "read",
            "Need for incident response investigation.", 60
        )
        assert req["status"] == "pending"
        assert req["principal"] == "agent-001"
        assert req["resource"] == "secrets/db-prod"
        assert req["action"] == "read"

    def test_request_id_is_valid_uuid(self):
        req = create_access_request(
            "agent-001", "secrets/db-prod", "read",
            "Incident response justification here.", 60
        )
        parsed = uuid.UUID(req["request_id"])
        assert str(parsed) == req["request_id"]

    def test_initial_status_is_pending(self):
        req = create_access_request(
            "agent-001", "policy-corpus", "read",
            "Policy corpus access for compliance report.", 30
        )
        assert req["status"] == "pending"

    def test_expires_at_matches_duration(self):
        req = create_access_request(
            "agent-001", "docs-api", "read",
            "Reading policy docs for evaluation.", 60
        )
        created = datetime.fromisoformat(req["created_at"])
        expires = datetime.fromisoformat(req["expires_at"])
        delta_seconds = (expires - created).total_seconds()
        assert abs(delta_seconds - 3600) < 5

    def test_duration_480_minutes_is_maximum(self):
        req = create_access_request(
            "agent-001", "res", "read",
            "Maximum duration access request.", 480
        )
        assert req["duration_minutes"] == 480

    def test_duration_1_minute_is_minimum(self):
        req = create_access_request(
            "agent-001", "res", "read",
            "Minimum duration access request.", 1
        )
        assert req["duration_minutes"] == 1

    def test_duration_481_raises_value_error(self):
        with pytest.raises(ValueError, match="duration_minutes"):
            create_access_request("agent-001", "res", "read", "Valid justification here.", 481)

    def test_duration_0_raises_value_error(self):
        with pytest.raises(ValueError, match="duration_minutes"):
            create_access_request("agent-001", "res", "read", "Valid justification here.", 0)

    def test_duration_negative_raises_value_error(self):
        with pytest.raises(ValueError, match="duration_minutes"):
            create_access_request("agent-001", "res", "read", "Valid justification here.", -10)

    def test_empty_principal_raises_value_error(self):
        with pytest.raises(ValueError, match="principal"):
            create_access_request("", "res", "read", "Valid justification here.", 60)

    def test_whitespace_only_principal_raises_value_error(self):
        with pytest.raises(ValueError, match="principal"):
            create_access_request("   ", "res", "read", "Valid justification here.", 60)

    def test_empty_resource_raises_value_error(self):
        with pytest.raises(ValueError, match="resource"):
            create_access_request("agent-001", "", "read", "Valid justification here.", 60)

    def test_invalid_action_raises_value_error(self):
        with pytest.raises(ValueError, match="action"):
            create_access_request("agent-001", "res", "delete", "Valid justification here.", 60)

    def test_unknown_action_raises_value_error(self):
        with pytest.raises(ValueError, match="action"):
            create_access_request("agent-001", "res", "FULL_ACCESS", "Valid justification.", 60)

    def test_short_justification_raises_value_error(self):
        with pytest.raises(ValueError, match="justification"):
            create_access_request("agent-001", "res", "read", "too short", 60)

    def test_justification_exactly_10_chars_is_valid(self):
        req = create_access_request("agent-001", "res", "read", "1234567890", 60)
        assert req["status"] == "pending"

    def test_all_valid_actions_accepted(self):
        for action in VALID_ACTIONS:
            req = create_access_request(
                "agent-001", "res", action,
                "Valid justification for action test.", 60
            )
            assert req["action"] == action

    def test_two_requests_have_different_ids(self):
        r1 = create_access_request("agent-001", "res", "read", "Valid justification text here.", 60)
        r2 = create_access_request("agent-001", "res", "read", "Valid justification text here.", 60)
        assert r1["request_id"] != r2["request_id"]
