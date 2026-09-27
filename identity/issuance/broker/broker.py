"""SVID Issuance Broker — FastAPI service for SPIFFE SVID issuance to registered agents."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import httpx
import structlog
import yaml
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

logger = structlog.get_logger(__name__)

SPIRE_AGENT_SOCKET = os.getenv("SPIRE_AGENT_SOCKET", "/tmp/spire-agent/public/api.sock")
REGISTRY_PATH = Path(
    os.getenv(
        "AGENT_REGISTRY_PATH",
        str(Path(__file__).parent.parent.parent / "registry" / "agents"),
    )
)


app = FastAPI(title="SVID Issuance Broker", version="0.1.0")


class SVIDRequest(BaseModel):
    agent_id: str
    audience: list[str] = []


class SVIDResponse(BaseModel):
    svid: str
    bundle: str
    ttl_seconds: int
    agent_id: str
    spiffe_id: str


class ValidateRequest(BaseModel):
    svid: str


def _load_agent_registry() -> dict[str, dict]:
    """Load agent profiles from YAML files in the registry directory."""
    agents: dict[str, dict] = {}
    if not REGISTRY_PATH.exists():
        logger.warning("registry_path_not_found", path=str(REGISTRY_PATH))
        return agents
    for yaml_file in REGISTRY_PATH.glob("*.yaml"):
        try:
            profile = yaml.safe_load(yaml_file.read_text())
            agents[profile["agent_id"]] = profile
        except Exception as exc:
            logger.error("failed_to_load_agent_profile", file=str(yaml_file), error=str(exc))
    return agents


@app.post("/issue", response_model=SVIDResponse)
async def issue_svid(request: SVIDRequest) -> SVIDResponse:
    """Issue a SPIFFE SVID to a registered agent.

    Validates the agent_id against the registry and calls the SPIRE
    workload API to obtain a valid SVID.
    """
    registry = _load_agent_registry()

    if request.agent_id not in registry:
        raise HTTPException(
            status_code=404,
            detail=f"Agent {request.agent_id!r} not found in registry.",
        )

    profile = registry[request.agent_id]
    spiffe_id = profile["svid_uri"]

    # In production: call SPIRE agent workload API via Unix socket
    # For environments without SPIRE: return a structured mock response
    spire_available = Path(SPIRE_AGENT_SOCKET).exists()

    if spire_available:
        try:
            async with httpx.AsyncClient(
                transport=httpx.AsyncHTTPTransport(uds=SPIRE_AGENT_SOCKET)
            ) as client:
                resp = await client.post(
                    "http://localhost/workload-api/svid",
                    json={"spiffe_id": spiffe_id, "audience": request.audience},
                    timeout=10.0,
                )
                resp.raise_for_status()
                data = resp.json()
                return SVIDResponse(
                    svid=data["svid"],
                    bundle=data["bundle"],
                    ttl_seconds=data.get("ttl_seconds", 1800),
                    agent_id=request.agent_id,
                    spiffe_id=spiffe_id,
                )
        except Exception as exc:
            logger.error("spire_workload_api_error", error=str(exc))
            raise HTTPException(status_code=503, detail="SPIRE workload API unavailable")
    else:
        # Development/testing: return well-formed stub
        logger.warning(
            "spire_socket_not_found_returning_stub",
            socket=SPIRE_AGENT_SOCKET,
        )
        tier = profile.get("tier", "T1")
        ttl_map = {"T0": 3600, "T1": 1800, "T2": 900}
        return SVIDResponse(
            svid=f"stub-svid-{request.agent_id}",
            bundle="stub-bundle",
            ttl_seconds=ttl_map.get(tier, 1800),
            agent_id=request.agent_id,
            spiffe_id=spiffe_id,
        )


@app.post("/validate")
async def validate_svid(request: ValidateRequest) -> dict[str, Any]:
    """Validate a presented SVID.

    Returns the parsed SPIFFE ID and expiry if valid.
    """
    svid = request.svid

    # Stub: in production, parse the X.509 SVID and verify the chain
    if svid.startswith("stub-svid-"):
        agent_id = svid[len("stub-svid-"):]
        registry = _load_agent_registry()
        if agent_id in registry:
            return {
                "valid": True,
                "spiffe_id": registry[agent_id]["svid_uri"],
                "agent_id": agent_id,
                "expires_in_seconds": 1800,
            }

    if not svid:
        return {"valid": False, "reason": "Empty SVID"}

    return {
        "valid": False,
        "reason": "SVID validation requires SPIRE workload API",
    }


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "spire_socket_available": Path(SPIRE_AGENT_SOCKET).exists()}
