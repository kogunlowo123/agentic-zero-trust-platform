import os

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from agent_runtime.tools.base import BaseTool

_API_URL = os.environ.get("API_URL", "http://api:8000")


class PostureCheckTool(BaseTool):
    """Check device/identity posture signals for a principal."""

    @property
    def name(self) -> str:
        return "posture_check"

    @property
    def description(self) -> str:
        return (
            "Retrieve the current posture score and risk signals for a given principal. "
            "Returns a PostureScore with score, risk_level, and detailed signals."
        )

    @property
    def schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "principal": {
                    "type": "string",
                    "description": "The principal ID to check posture for.",
                }
            },
            "required": ["principal"],
        }

    async def call(self, principal: str) -> dict:
        return await posture_check_tool(principal=principal)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    reraise=True,
)
async def posture_check_tool(principal: str) -> dict:
    """Retrieve posture signals for a principal from the platform API service.

    Makes a GET request to ``API_URL/api/v1/posture/{principal}`` and
    returns a normalised PostureScore dict.

    Args:
        principal: The principal ID (user UPN, service account, etc.).

    Returns:
        A dict matching the PostureScore contract:
            - principal (str)
            - score (float, 0-100)
            - risk_level (str, one of 'LOW'|'MEDIUM'|'HIGH'|'CRITICAL')
            - signals (dict): raw signal values keyed by signal name.

    Raises:
        RuntimeError: On HTTP error or unreachable API service.
    """
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            response = await client.get(
                f"{_API_URL}/api/v1/posture/{principal}",
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(
                f"Posture check failed for '{principal}' "
                f"with status {exc.response.status_code}: {exc.response.text}"
            ) from exc
        except httpx.RequestError as exc:
            raise RuntimeError(
                f"Failed to reach API service at {_API_URL}: {exc}"
            ) from exc

        body = response.json()

    score = float(body.get("score", 0.0))
    risk_level = body.get("risk_level") or _score_to_risk_level(score)

    return {
        "principal": principal,
        "score": score,
        "risk_level": risk_level,
        "signals": body.get("signals", {}),
    }


def _score_to_risk_level(score: float) -> str:
    """Derive risk level from a numeric posture score."""
    if score >= 80:
        return "LOW"
    if score >= 60:
        return "MEDIUM"
    if score >= 40:
        return "HIGH"
    return "CRITICAL"
