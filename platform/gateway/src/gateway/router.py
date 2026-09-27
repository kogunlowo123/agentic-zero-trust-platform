"""FastAPI router for the LLM gateway.

Exposes POST /v1/chat/completions with:
  - Bearer-token authentication
  - Per-user daily budget enforcement
  - Primary/fallback provider routing (Azure OpenAI -> Vertex AI)
  - Structured audit logging
"""

import os
import time
import uuid
from typing import Annotated

import litellm
import structlog
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from gateway.audit_log import AuditLogger
from gateway.budget_enforcer import BudgetEnforcer
from gateway.providers.azure_openai import AzureOpenAIProvider

log = structlog.get_logger(__name__)

_VERTEX_PROJECT = os.environ.get("VERTEX_PROJECT_ID", "")
_VERTEX_LOCATION = os.environ.get("VERTEX_LOCATION", "us-central1")
_MAX_DAILY_USD = float(os.environ.get("GATEWAY_MAX_DAILY_USD", "100.0"))

router = APIRouter()
_bearer = HTTPBearer()

# Module-level singletons (wired up by the FastAPI application factory)
_azure_provider = AzureOpenAIProvider()
_audit_logger = AuditLogger()


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class ChatMessage(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: str = Field(default="gpt-4o")
    messages: list[ChatMessage]
    max_tokens: int = Field(default=4096, ge=1, le=8192)
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    stream: bool = Field(default=False)


class ChatCompletionResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    model: str
    content: str
    usage: dict
    provider: str


# ---------------------------------------------------------------------------
# Auth helper
# ---------------------------------------------------------------------------

def _extract_user_id(credentials: HTTPAuthorizationCredentials) -> str:
    """Extract user identifier from bearer token.

    In production this should validate a JWT/OIDC token.  Here we use
    the token value directly as the user ID (suitable for service accounts
    using opaque API keys).
    """
    token = credentials.credentials
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
        )
    # Real validation: decode JWT, call token introspection endpoint, etc.
    return token  # treat token as opaque user-id for this layer


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------

@router.post("/v1/chat/completions", response_model=ChatCompletionResponse)
async def chat_completions(
    request: ChatCompletionRequest,
    http_request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
) -> ChatCompletionResponse:
    """Route a chat completion request to the primary or fallback LLM provider.

    Flow:
      1. Authenticate caller via Bearer token.
      2. Estimate cost and check daily budget.
      3. Attempt Azure OpenAI (primary).
      4. On failure, fall back to Vertex AI.
      5. Log audit record and return response.
    """
    request_id = str(uuid.uuid4())
    user_id = _extract_user_id(credentials)

    # Budget check — estimate using gpt-4o input costs
    estimated_input_tokens = sum(len(m.content.split()) * 1.3 for m in request.messages)
    estimated_cost = (estimated_input_tokens / 1000) * 0.005  # gpt-4o rate

    budget_enforcer: BudgetEnforcer | None = getattr(http_request.app.state, "budget_enforcer", None)
    if budget_enforcer is not None:
        within_budget = await budget_enforcer.check_and_deduct(user_id, estimated_cost)
        if not within_budget:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail="Daily budget exceeded",
            )

    messages = [{"role": m.role, "content": m.content} for m in request.messages]
    start_ts = time.monotonic()
    provider_used = "azure_openai"
    result: dict | None = None
    last_error: str = ""

    # Primary: Azure OpenAI
    try:
        result = await _azure_provider.complete(
            messages=messages,
            model=request.model,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
        )
        provider_used = "azure_openai"
    except Exception as azure_exc:  # noqa: BLE001
        last_error = str(azure_exc)
        log.warning(
            "azure_openai_failed",
            request_id=request_id,
            user_id=user_id,
            error=last_error,
        )

        # Fallback: Vertex AI via LiteLLM
        try:
            vertex_model = f"vertex_ai/gemini-pro"
            if _VERTEX_PROJECT:
                vertex_response = await litellm.acompletion(
                    model=vertex_model,
                    messages=messages,
                    max_tokens=request.max_tokens,
                    temperature=request.temperature,
                    vertex_project=_VERTEX_PROJECT,
                    vertex_location=_VERTEX_LOCATION,
                )
                content = vertex_response.choices[0].message.content or ""
                usage_obj = vertex_response.usage or {}
                result = {
                    "content": content,
                    "model": vertex_model,
                    "usage": {
                        "prompt_tokens": getattr(usage_obj, "prompt_tokens", 0),
                        "completion_tokens": getattr(usage_obj, "completion_tokens", 0),
                        "total_tokens": getattr(usage_obj, "total_tokens", 0),
                    },
                }
                provider_used = "vertex_ai"
            else:
                raise RuntimeError("Vertex AI not configured — VERTEX_PROJECT_ID missing")
        except Exception as vertex_exc:  # noqa: BLE001
            last_error = f"Azure: {azure_exc}; Vertex: {vertex_exc}"
            log.error(
                "all_providers_failed",
                request_id=request_id,
                user_id=user_id,
                error=last_error,
            )

    latency_ms = (time.monotonic() - start_ts) * 1000
    success = result is not None

    # Audit log
    await _audit_logger.log_request(
        user_id=user_id,
        model=request.model,
        tokens_in=result["usage"]["prompt_tokens"] if result else 0,
        tokens_out=result["usage"]["completion_tokens"] if result else 0,
        cost=estimated_cost,
        latency_ms=latency_ms,
        success=success,
        request_id=request_id,
        error=last_error if not success else None,
        provider=provider_used,
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"All providers failed: {last_error}",
        )

    return ChatCompletionResponse(
        id=request_id,
        model=result["model"],
        content=result["content"],
        usage=result["usage"],
        provider=provider_used,
    )
