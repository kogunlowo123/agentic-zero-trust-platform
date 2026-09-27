from __future__ import annotations

from opentelemetry import trace
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

tracer = trace.get_tracer(__name__)


class TracingMiddleware(BaseHTTPMiddleware):
    """OpenTelemetry tracing middleware that enriches spans with zero-trust attributes."""

    async def dispatch(self, request: Request, call_next):
        span = trace.get_current_span()
        if span.is_recording():
            span.set_attribute("http.method", request.method)
            span.set_attribute("http.path", request.url.path)
            span.set_attribute("http.host", request.url.hostname or "unknown")

        response = await call_next(request)

        # Enrich span with principal/tenant after auth middleware has run
        if span.is_recording():
            principal = getattr(request.state, "principal", None)
            tier = getattr(request.state, "tier", None)
            if principal:
                span.set_attribute("zero_trust.principal", principal)
            if tier:
                span.set_attribute("zero_trust.tier", tier)
            span.set_attribute("http.status_code", response.status_code)

        return response
