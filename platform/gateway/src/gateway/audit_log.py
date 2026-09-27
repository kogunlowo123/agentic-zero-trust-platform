from datetime import datetime, timezone

import structlog

_log = structlog.get_logger(__name__)


class AuditLogger:
    """Structured JSON audit logger for LLM gateway requests.

    Emits one structured log event per request via structlog.  In production
    the structlog pipeline should be configured to emit JSON to stdout or to
    an OpenTelemetry log exporter.

    Args:
        service_name: Identifies the emitting service in every log record.
                      Defaults to 'llm-gateway'.
    """

    def __init__(self, service_name: str = "llm-gateway") -> None:
        self._service = service_name

    async def log_request(
        self,
        user_id: str,
        model: str,
        tokens_in: int,
        tokens_out: int,
        cost: float,
        latency_ms: float,
        success: bool,
        *,
        request_id: str | None = None,
        error: str | None = None,
        provider: str | None = None,
    ) -> None:
        """Emit a structured audit log record for a completed gateway request.

        Args:
            user_id: Authenticated caller identity.
            model: The LLM model string used (e.g. 'azure/gpt-4o').
            tokens_in: Number of prompt tokens consumed.
            tokens_out: Number of completion tokens generated.
            cost: Estimated USD cost of the request.
            latency_ms: End-to-end request latency in milliseconds.
            success: True if the upstream provider returned a valid completion.
            request_id: Optional correlation ID for tracing.
            error: Error message when success is False.
            provider: Name of the provider that served the request
                      (e.g. 'azure_openai', 'vertex_ai').
        """
        record: dict = {
            "event": "gateway.request",
            "service": self._service,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user_id": user_id,
            "model": model,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "total_tokens": tokens_in + tokens_out,
            "cost_usd": round(cost, 6),
            "latency_ms": round(latency_ms, 2),
            "success": success,
        }
        if request_id:
            record["request_id"] = request_id
        if provider:
            record["provider"] = provider
        if not success and error:
            record["error"] = error

        if success:
            _log.info(**record)
        else:
            _log.warning(**record)
