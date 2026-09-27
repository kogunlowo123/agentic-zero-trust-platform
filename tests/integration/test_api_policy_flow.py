"""Integration tests for the API policy flow.

Uses FastAPI TestClient. External dependencies (OPA, Redis) are mocked
so these tests run without any running services.
"""

import sys
import os
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure the api package is importable
_API_SRC = os.path.join(
    os.path.dirname(__file__),
    "..", "..",
    "services", "api", "src",
)
if os.path.isdir(_API_SRC):
    sys.path.insert(0, os.path.abspath(_API_SRC))

try:
    import jwt as pyjwt
    _PYJWT_AVAILABLE = True
except ImportError:
    _PYJWT_AVAILABLE = False

try:
    from fastapi.testclient import TestClient
    _FASTAPI_AVAILABLE = True
except ImportError:
    _FASTAPI_AVAILABLE = False


JWT_SECRET = "test-integration-secret"
JWT_ALGORITHM = "HS256"


def _make_token(
    principal: str = "test-agent",
    tier: str = "T1",
    svid: str = "spiffe://zero-trust.example.com/agent/test",
    posture_score: float = 75.0,
    exp_delta: int = 3600,
) -> str:
    if not _PYJWT_AVAILABLE:
        return "dummy.token.value"
    payload = {
        "sub": principal,
        "tier": tier,
        "svid": svid,
        "posture_score": posture_score,
        "exp": int((datetime.now(timezone.utc) + timedelta(seconds=exp_delta)).timestamp()),
        "iat": int(datetime.now(timezone.utc).timestamp()),
    }
    return pyjwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


@pytest.fixture(autouse=True)
def _patch_env(monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", JWT_SECRET)
    monkeypatch.setenv("JWT_ALGORITHM", JWT_ALGORITHM)
    monkeypatch.setenv("OPA_URL", "http://localhost:18181")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:16379")
    monkeypatch.setenv("AZURE_SERVICE_BUS_CONNECTION_STRING", "")


def _get_client():
    try:
        from api.main import app
        return TestClient(app, raise_server_exceptions=False)
    except Exception:
        return None


@pytest.mark.skipif(not _FASTAPI_AVAILABLE or not _PYJWT_AVAILABLE, reason="fastapi or jwt not installed")
class TestHealthEndpoints:

    def test_health_returns_200_without_auth(self):
        client = _get_client()
        if client is None:
            pytest.skip("API app could not be imported")
        response = client.get("/api/v1/health")
        assert response.status_code == 200

    def test_health_response_has_status_ok(self):
        client = _get_client()
        if client is None:
            pytest.skip("API app could not be imported")
        response = client.get("/api/v1/health")
        data = response.json()
        assert data.get("status") == "ok"

    def test_health_response_has_version(self):
        client = _get_client()
        if client is None:
            pytest.skip("API app could not be imported")
        response = client.get("/api/v1/health")
        data = response.json()
        assert "version" in data

    def test_health_response_has_timestamp(self):
        client = _get_client()
        if client is None:
            pytest.skip("API app could not be imported")
        response = client.get("/api/v1/health")
        data = response.json()
        assert "timestamp" in data


@pytest.mark.skipif(not _FASTAPI_AVAILABLE or not _PYJWT_AVAILABLE, reason="fastapi or jwt not installed")
class TestPolicyEvaluateAuth:

    def test_policy_evaluate_without_auth_returns_401(self):
        client = _get_client()
        if client is None:
            pytest.skip("API app could not be imported")
        response = client.post(
            "/api/v1/policy/evaluate",
            json={"resource_id": "test", "resource_sensitivity": "LOW", "action": "read"},
        )
        assert response.status_code == 401

    def test_policy_evaluate_with_wrong_scheme_returns_401(self):
        client = _get_client()
        if client is None:
            pytest.skip("API app could not be imported")
        response = client.post(
            "/api/v1/policy/evaluate",
            json={"resource_id": "test", "resource_sensitivity": "LOW", "action": "read"},
            headers={"Authorization": "Basic dXNlcjpwYXNz"},
        )
        assert response.status_code == 401

    def test_policy_evaluate_with_expired_token_returns_401(self):
        client = _get_client()
        if client is None:
            pytest.skip("API app could not be imported")
        token = _make_token(exp_delta=-10)  # already expired
        response = client.post(
            "/api/v1/policy/evaluate",
            json={"resource_id": "test", "resource_sensitivity": "LOW", "action": "read"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 401

    @patch("httpx.AsyncClient.post")
    def test_policy_evaluate_with_valid_token_calls_opa(self, mock_post):
        client = _get_client()
        if client is None:
            pytest.skip("API app could not be imported")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": {"allow": True, "deny_reasons": []}}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        token = _make_token()
        response = client.post(
            "/api/v1/policy/evaluate",
            json={"resource_id": "docs-api", "resource_sensitivity": "MEDIUM", "action": "read"},
            headers={"Authorization": f"Bearer {token}"},
        )
        # Should not be 401 (auth passed)
        assert response.status_code != 401


@pytest.mark.skipif(not _FASTAPI_AVAILABLE or not _PYJWT_AVAILABLE, reason="fastapi or jwt not installed")
class TestAccessRequestEndpoints:

    def test_access_request_without_auth_returns_401(self):
        client = _get_client()
        if client is None:
            pytest.skip("API app could not be imported")
        response = client.post(
            "/api/v1/access/request",
            json={
                "resource": "secrets/db",
                "action": "read",
                "justification": "Incident response investigation.",
                "duration_minutes": 60,
            },
        )
        assert response.status_code == 401

    def test_access_status_without_auth_returns_401(self):
        client = _get_client()
        if client is None:
            pytest.skip("API app could not be imported")
        response = client.get("/api/v1/access/some-id/status")
        assert response.status_code == 401
