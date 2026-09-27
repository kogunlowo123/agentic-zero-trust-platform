# Agentic Zero Trust Platform

[![CI](https://github.com/kogunlowo123/agentic-zero-trust-platform/actions/workflows/ci.yml/badge.svg)](https://github.com/kogunlowo123/agentic-zero-trust-platform/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![Code Style](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![Security](https://img.shields.io/badge/security-bandit-yellow.svg)](https://bandit.readthedocs.io/)
[![OpenTelemetry](https://img.shields.io/badge/observability-OpenTelemetry-blue.svg)](https://opentelemetry.io/)

An enterprise-grade security platform implementing Zero Trust Architecture for AI agents. Every agent action is continuously verified, every resource access is policy-controlled, and every decision is audited in real time.

## Overview

The Agentic Zero Trust Platform enforces the principle of "never trust, always verify" across all AI agent interactions. It provides:

- **Continuous identity verification** for every agent request
- **Policy-as-code** enforcement using Open Policy Agent (OPA)
- **Dynamic risk scoring** based on behavioral signals and context
- **Immutable audit logs** for compliance and forensics
- **Just-in-time access** with time-bounded permissions
- **Retrieval-Augmented Generation (RAG)** with access-controlled vector stores

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        API Gateway (FastAPI)                     │
│                     Port 8000 | mTLS | JWT                       │
└───────────────────┬────────────────────────────────┬────────────┘
                    │                                │
        ┌───────────▼──────────┐       ┌─────────────▼──────────┐
        │   Identity Service   │       │   Policy Engine (OPA)  │
        │  JWT · OIDC · RBAC   │       │  Rego · POST /v1/data  │
        └───────────┬──────────┘       └─────────────┬──────────┘
                    │                                │
        ┌───────────▼──────────┐       ┌─────────────▼──────────┐
        │    Agent Runtime     │       │      RAG Core           │
        │  LangGraph · LiteLLM │       │  OpenSearch · Vectors   │
        └───────────┬──────────┘       └─────────────┬──────────┘
                    │                                │
        ┌───────────▼────────────────────────────────▼──────────┐
        │              Data Layer                                │
        │     PostgreSQL + pgvector │ Redis │ OpenSearch         │
        └──────────────────────────────────────────────────────-─┘
                    │
        ┌───────────▼──────────────────────────┐
        │   SIEM / Observability               │
        │  OpenTelemetry · Logs · Metrics      │
        └──────────────────────────────────────┘
```

### Components

| Component | Description | Technology |
|-----------|-------------|------------|
| **API Gateway** | Central entry point, request routing, rate limiting | FastAPI, uvicorn |
| **Policy Engine** | Policy evaluation using Open Policy Agent | OPA 0.63+, Rego |
| **Identity Service** | Agent identity management, JWT issuance, OIDC | Python JWT, Azure AD |
| **Agent Runtime** | Orchestrated agent execution with guardrails | LangGraph 0.2+, LiteLLM 1.40+ |
| **RAG Core** | Vector search with access-controlled document retrieval | OpenSearch, pgvector |
| **Observability** | Distributed tracing, metrics, structured logging | OpenTelemetry, OTLP |

## Quick Start

### Prerequisites

- Docker 24+ and Docker Compose 2.24+
- Python 3.12+ and [uv](https://docs.astral.sh/uv/)
- Azure subscription (for Azure OpenAI, Key Vault, Service Bus)

### 1. Clone the Repository

```bash
git clone https://github.com/kogunlowo123/agentic-zero-trust-platform.git
cd agentic-zero-trust-platform
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your Azure credentials and service endpoints
```

### 3. Start All Services

```bash
docker-compose up -d
```

### 4. Verify Deployment

```bash
curl http://localhost:8000/health
# {"status": "healthy", "version": "0.1.0"}

curl http://localhost:8181/health
# {"status": "ok"}
```

### 5. Run Policy Evaluation

```bash
curl -X POST http://localhost:8000/api/v1/policy/evaluate \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "principal": "agent:summarizer-v1",
    "resource": "document-store:confidential",
    "action": "read",
    "justification": "Summarizing Q4 reports for executive dashboard",
    "duration_minutes": 30
  }'
```

### 6. Local Development

```bash
uv sync
uv run pre-commit install
make dev
```

## API Reference

Base URL: `http://localhost:8000/api/v1`

### Policy Evaluation

#### `POST /policy/evaluate`

Evaluate whether a principal is allowed to perform an action on a resource.

**Request Body** (`AccessRequest`):
```json
{
  "principal": "agent:data-pipeline-v2",
  "resource": "database:customer-records",
  "action": "read",
  "justification": "Generating monthly usage report",
  "duration_minutes": 60
}
```

**Response** (`PolicyDecision`):
```json
{
  "allowed": true,
  "reasons": ["principal has read access to customer-records", "posture score 87/100 within threshold"],
  "principal": "agent:data-pipeline-v2",
  "timestamp": "2024-01-15T14:30:00Z",
  "decision_id": "dec_01HN4X7K2MZPQ8R9STUVWXYZ0"
}
```

### Agent Registration

#### `POST /agents/register`

Register a new agent identity with the platform.

**Request Body**:
```json
{
  "agent_id": "agent:summarizer-v1",
  "display_name": "Document Summarizer",
  "version": "1.0.0",
  "capabilities": ["read:documents", "write:summaries"],
  "owner": "team:data-platform"
}
```

#### `GET /agents/{agent_id}/posture`

Retrieve the current security posture score for an agent.

**Response** (`PostureScore`):
```json
{
  "principal": "agent:summarizer-v1",
  "score": 87.5,
  "risk_level": "LOW",
  "signals": {
    "anomaly_score": 0.12,
    "policy_violations_24h": 0,
    "access_entropy": 0.35,
    "behavior_drift": 0.08
  }
}
```

### Access Requests

#### `POST /access/request`

Request time-bounded access to a protected resource.

#### `DELETE /access/{request_id}/revoke`

Revoke an active access grant before expiry.

#### `GET /access/history`

Retrieve access request history for the authenticated principal.

## Environment Variables

Copy `.env.example` to `.env` and populate all required values.

### Azure OpenAI

| Variable | Description | Example |
|----------|-------------|---------|
| `AZURE_OPENAI_ENDPOINT` | Azure OpenAI resource endpoint | `https://myorg.openai.azure.com/` |
| `AZURE_OPENAI_API_KEY` | Azure OpenAI API key | `abc123...` |
| `AZURE_OPENAI_DEPLOYMENT` | Model deployment name | `gpt-4o` |

### Azure Identity

| Variable | Description |
|----------|-------------|
| `AZURE_TENANT_ID` | Azure AD tenant ID |
| `AZURE_CLIENT_ID` | Service principal client ID |
| `AZURE_CLIENT_SECRET` | Service principal client secret |

### Data Services

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://ztplatform:secret@localhost:5432/ztplatform` |
| `OPENSEARCH_URL` | OpenSearch endpoint | `http://localhost:9200` |
| `REDIS_URL` | Redis connection string | `redis://localhost:6379/0` |

### Security

| Variable | Description |
|----------|-------------|
| `OPA_URL` | OPA server endpoint | `http://opa:8181` |
| `JWT_SECRET_KEY` | Secret for JWT signing (RS256 recommended in prod) |
| `JWT_ALGORITHM` | JWT algorithm | `HS256` |

### Observability

| Variable | Description | Default |
|----------|-------------|---------|
| `OTEL_ENDPOINT` | OTLP collector endpoint | `http://localhost:4317` |
| `LOG_LEVEL` | Logging verbosity | `INFO` |
| `ENVIRONMENT` | Deployment environment | `development` |

### Azure Additional Services

| Variable | Description |
|----------|-------------|
| `AZURE_AI_SEARCH_ENDPOINT` | Azure AI Search endpoint |
| `AZURE_AI_SEARCH_KEY` | Azure AI Search admin key |
| `AZURE_SERVICE_BUS_CONNECTION_STRING` | Service Bus namespace connection |
| `AZURE_KEY_VAULT_URL` | Key Vault URL for secret rotation |

## Development

### Running Tests

```bash
make test              # All tests
make test-unit         # Unit tests only
make test-integration  # Integration tests (requires Docker services)
make test-security     # Security-focused tests with bandit
```

### Linting and Formatting

```bash
make lint    # ruff check + mypy type checking
make format  # ruff format
```

### Building Docker Images

```bash
make build   # Build all service images
make push    # Push to configured registry
```

### Infrastructure

```bash
make terraform-init   # Initialize Terraform providers
make terraform-plan   # Preview infrastructure changes
make terraform-apply  # Apply infrastructure changes
```

## Security

See [SECURITY.md](SECURITY.md) for the vulnerability reporting process and security policy.

The platform enforces Zero Trust principles:
1. **Never trust, always verify** — every request is authenticated and authorized
2. **Least privilege access** — time-bounded, just-in-time permissions
3. **Assume breach** — all traffic is inspected, all actions are audited
4. **Continuous verification** — posture scores updated in real time

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for the development workflow, code style requirements, and PR process.

## License

This project is licensed under the Apache License 2.0. See [LICENSE](LICENSE) for the full text.

Copyright 2024 agentic-zero-trust-platform contributors.
