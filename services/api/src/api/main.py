from __future__ import annotations

import os

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.middleware.auth import AuthMiddleware
from api.middleware.ratelimit import RateLimitMiddleware
from api.middleware.tenant import TenantMiddleware
from api.middleware.tracing import TracingMiddleware
from api.routes.v1 import access, health, policy, posture

logger = structlog.get_logger(__name__)


def _configure_logging() -> None:
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            structlog.stdlib.NAME_TO_LEVEL.get(os.getenv("LOG_LEVEL", "INFO").lower(), 20)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def _configure_otel() -> None:
    otel_endpoint = os.getenv("OTEL_ENDPOINT", "")
    if not otel_endpoint:
        return
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        resource = Resource.create(
            {
                "service.name": "agentic-zero-trust-api",
                "service.version": "0.1.0",
                "deployment.environment": os.getenv("ENVIRONMENT", "development"),
            }
        )
        provider = TracerProvider(resource=resource)
        exporter = OTLPSpanExporter(endpoint=otel_endpoint, insecure=True)
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)
        logger.info("otel_configured", endpoint=otel_endpoint)
    except Exception as exc:
        logger.warning("otel_setup_failed", error=str(exc))


def create_app() -> FastAPI:
    _configure_logging()
    _configure_otel()

    app = FastAPI(
        title="Agentic Zero Trust Platform",
        description=(
            "Enterprise AI security platform implementing Zero Trust for AI agents. "
            "OPA/Rego policy enforcement, posture assessment, and JIT access management."
        ),
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # Middleware — applied in reverse order (last added = first executed)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(TracingMiddleware)
    app.add_middleware(
        RateLimitMiddleware,
        requests_per_minute=int(os.getenv("RATE_LIMIT_PER_MINUTE", "60")),
    )
    app.add_middleware(TenantMiddleware)
    app.add_middleware(AuthMiddleware)

    # Routers
    app.include_router(health.router, prefix="/api/v1")
    app.include_router(policy.router, prefix="/api/v1/policy")
    app.include_router(access.router, prefix="/api/v1/access")
    app.include_router(posture.router, prefix="/api/v1/posture")

    # OpenTelemetry FastAPI instrumentation (if SDK is available)
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor.instrument_app(app)
    except ImportError:
        pass

    @app.on_event("startup")
    async def startup() -> None:
        logger.info(
            "platform_api_started",
            environment=os.getenv("ENVIRONMENT", "development"),
            opa_url=os.getenv("OPA_URL", "http://opa:8181"),
        )

    @app.on_event("shutdown")
    async def shutdown() -> None:
        logger.info("platform_api_shutdown")

    return app


app = create_app()
