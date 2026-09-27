# Changelog

All notable changes to the Agentic Zero Trust Platform will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Multi-tenant OPA policy namespacing for isolated policy evaluation per tenant
- Azure Service Bus integration for async policy violation event streaming
- Agent behaviour anomaly detection using rolling baseline comparison
- SCIM 2.0 endpoint for automated agent provisioning and deprovisioning
- Helm chart for Kubernetes deployment (`deploy/helm/agentic-zero-trust`)
- Terraform modules for Azure AKS, Key Vault, and Service Bus provisioning
- gRPC transport layer for high-throughput inter-service communication
- Policy simulation endpoint (`POST /api/v1/policy/simulate`) for dry-run evaluation
- Bulk access revocation API for incident response workflows
- OpenSearch index lifecycle management for audit log retention policies

### Changed
- PostureScore risk thresholds are now configurable per agent class via OPA policy
- JWT expiry defaults reduced from 3600s to 900s for short-lived agent tokens
- Increased minimum TLS version from 1.2 to 1.3 across all service listeners

### Security
- Patched parameter injection vector in `/agents/register` endpoint (input sanitisation)

## [0.1.0] - 2024-01-15

### Added

#### Zero Trust Policy Engine
- Integrated Open Policy Agent (OPA) 0.63 as the central policy decision point
- Rego bundle `zerotrust` with rules for principal authorization, resource access, and action allowlisting
- Policy evaluation endpoint `POST /api/v1/policy/evaluate` returning `PolicyDecision` schema
- OPA policy reload via bundle server — no restart required on policy update
- CloudEvent emission on policy denial: type `policy.violation`, source `agentic-zero-trust/policy-enforcer`
- Decision audit trail: every `PolicyDecision` persisted to PostgreSQL and indexed in OpenSearch

#### Agent Identity Management
- Agent registration API (`POST /api/v1/agents/register`) with unique identity assignment
- JWT issuance endpoint with configurable algorithm (`JWT_ALGORITHM`) and expiry
- Agent metadata store: capabilities, owner, version, registration timestamp
- RBAC role definitions: `agent:read-only`, `agent:read-write`, `agent:privileged`
- Principal naming convention enforced: `agent:<name>-<version>` slug format

#### Authentication and Authorization
- JWT middleware on all protected API routes; unauthenticated requests return 401
- RS256 support in production; HS256 available for development (`JWT_ALGORITHM`)
- Token refresh endpoint with sliding expiry for long-running agent sessions
- OIDC integration with Azure Active Directory for human operator authentication
- API key support for service-to-service calls in CI/CD pipelines

#### Policy Evaluation API
- `AccessRequest` model: `principal`, `resource`, `action`, `justification`, `duration_minutes`
- `PolicyDecision` response: `allowed`, `reasons`, `principal`, `timestamp`, `decision_id`
- OPA endpoint proxied at `POST http://opa:8181/v1/data/zerotrust/allow`
- Request context enrichment: caller IP, user-agent, trace ID injected before OPA evaluation
- Batch evaluation endpoint for evaluating multiple access requests in a single call

#### Posture Scoring
- `PostureScore` model: `principal`, `score` (0–100 float), `risk_level` (LOW/MEDIUM/HIGH/CRITICAL), `signals` dict
- Score calculation signals: anomaly score, policy violations (24h window), access entropy, behaviour drift
- Posture score cache in Redis with 60-second TTL
- Automatic session suspension when posture score falls below configurable threshold (default 60.0)
- Posture history endpoint: `GET /api/v1/agents/{agent_id}/posture/history`

#### Docker Compose Deployment
- Full stack `docker-compose.yml` with services: `api`, `opa`, `postgres`, `opensearch`, `redis`, `otel-collector`
- Health checks for all services with appropriate intervals and retry counts
- Isolated `zt-network` bridge network; no cross-container access outside defined links
- Persistent named volumes for PostgreSQL data, OpenSearch indices, and OPA bundle cache
- `.env.example` template covering all required configuration variables

#### Azure OpenAI Integration
- LiteLLM 1.40 proxy configured for Azure OpenAI (`AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_DEPLOYMENT`)
- Streaming response support via SSE on `/api/v1/agents/{agent_id}/invoke`
- Per-request token usage metering stored in PostgreSQL for cost attribution
- Retry logic with exponential backoff on transient Azure API errors (429, 503)

#### OpenSearch Vector Store for RAG
- RAG Core service using OpenSearch k-NN indices for document vector storage
- `pgvector` extension initialised on PostgreSQL for hybrid relational + vector queries
- Document ingestion pipeline: chunking, embedding via Azure OpenAI, indexing
- Access-controlled retrieval: documents tagged with `classification` and `allowed_principals`; OPA policy enforced at retrieval time
- Similarity search endpoint: `POST /api/v1/rag/search` with `top_k` and `min_score` parameters

#### OpenTelemetry Observability
- OpenTelemetry SDK instrumented in all services (traces, metrics, logs)
- OTLP exporter configured to push to `otel-collector` (`OTEL_ENDPOINT`)
- Custom spans on policy evaluation, agent invocation, and RAG retrieval
- Trace propagation via W3C TraceContext headers across all inter-service calls
- Prometheus metrics endpoint at `/metrics` on all services

#### CI/CD Foundation
- GitHub Actions CI workflow: lint, unit tests, integration tests, security scan
- Pre-commit configuration with ruff, mypy, bandit, and yaml/toml validators
- Makefile with targets for all common developer operations
- Dependabot configuration for Python, Terraform, Docker, and GitHub Actions

[Unreleased]: https://github.com/kogunlowo123/agentic-zero-trust-platform/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/kogunlowo123/agentic-zero-trust-platform/releases/tag/v0.1.0
