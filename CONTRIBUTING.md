# Contributing to Agentic Zero Trust Platform

Thank you for your interest in contributing. This guide covers the development environment setup, code standards, and the pull request process.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Development Environment Setup](#development-environment-setup)
- [Branch Naming Conventions](#branch-naming-conventions)
- [Commit Message Format](#commit-message-format)
- [Pull Request Process](#pull-request-process)
- [Code Style](#code-style)
- [Testing Requirements](#testing-requirements)
- [Pre-commit Hooks](#pre-commit-hooks)
- [Documentation](#documentation)

## Code of Conduct

Contributors are expected to maintain a professional and respectful environment. Harassment or discriminatory behaviour will not be tolerated. Report issues to security@example.com.

## Development Environment Setup

### Prerequisites

| Tool | Minimum Version | Install |
|------|----------------|---------|
| Python | 3.12 | [python.org](https://www.python.org/) |
| uv | 0.4+ | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| Docker | 24.0+ | [docker.com](https://www.docker.com/) |
| Docker Compose | 2.24+ | Bundled with Docker Desktop |
| Terraform | 1.8+ | [terraform.io](https://www.terraform.io/) |

### 1. Fork and Clone

```bash
# Fork the repository on GitHub, then:
git clone https://github.com/<your-username>/agentic-zero-trust-platform.git
cd agentic-zero-trust-platform
git remote add upstream https://github.com/kogunlowo123/agentic-zero-trust-platform.git
```

### 2. Install Python Dependencies

```bash
# Create the virtual environment and install all deps (including dev extras)
uv sync --all-extras

# Verify installation
uv run python --version
# Python 3.12.x
```

### 3. Configure Environment

```bash
cp .env.example .env
# Edit .env — at minimum set DATABASE_URL, OPA_URL, JWT_SECRET_KEY
```

### 4. Start Infrastructure Services

```bash
docker-compose up -d postgres opa opensearch redis
```

### 5. Run the API

```bash
uv run uvicorn services.api.main:app --reload --port 8000
```

### 6. Verify Setup

```bash
uv run pytest tests/unit/ -v
```

## Branch Naming Conventions

Branches must follow this naming scheme:

| Prefix | Use Case | Example |
|--------|----------|---------|
| `feat/` | New features | `feat/agent-posture-scoring` |
| `fix/` | Bug fixes | `fix/jwt-expiry-validation` |
| `chore/` | Maintenance, deps, CI | `chore/update-litellm-1.45` |
| `docs/` | Documentation only | `docs/api-reference-update` |
| `security/` | Security patches | `security/opa-policy-tightening` |
| `refactor/` | Code restructuring without behaviour change | `refactor/extract-policy-client` |
| `test/` | Adding or fixing tests | `test/integration-opa-coverage` |

Branch names must be lowercase, use hyphens (not underscores), and be descriptive but concise (≤60 characters).

## Commit Message Format

This project uses [Conventional Commits](https://www.conventionalcommits.org/). Every commit message must follow this format:

```
<type>(<scope>): <short description>

[optional body]

[optional footer(s)]
```

### Types

| Type | Description |
|------|-------------|
| `feat` | A new feature |
| `fix` | A bug fix |
| `chore` | Build system, dependencies, tooling |
| `docs` | Documentation changes only |
| `refactor` | Code change that is neither a bug fix nor a new feature |
| `test` | Adding or correcting tests |
| `security` | Security-related changes |
| `perf` | Performance improvements |
| `ci` | Changes to CI/CD configuration |

### Scopes

Common scopes: `api`, `policy`, `identity`, `rag`, `runtime`, `infra`, `deploy`, `tests`.

### Examples

```
feat(policy): add time-based access expiration to OPA rules

Implements duration_minutes enforcement in the zerotrust Rego bundle.
Policy decisions now include an expiry timestamp in the metadata block.

Closes #42
```

```
fix(identity): correct JWT algorithm validation order

RS256 was falling back to HS256 when the public key was misconfigured.
Now raises AuthenticationError explicitly.
```

```
security(api): enforce strict input validation on /policy/evaluate

Adds Pydantic v2 strict mode to AccessRequest model. Rejects requests
with extraneous fields to prevent parameter injection.

CVE-2024-XXXX
```

## Pull Request Process

1. **Sync with upstream** before opening a PR:
   ```bash
   git fetch upstream
   git rebase upstream/main
   ```

2. **Ensure all checks pass locally**:
   ```bash
   make lint
   make test
   ```

3. **Open the PR** against the `main` branch of the upstream repository.

4. **Fill in the PR template** completely. Incomplete templates will be returned for revision.

5. **Respond to review feedback** within 5 business days. Stale PRs (no activity for 14 days) will be closed.

6. **Squash and merge** is the merge strategy. The PR title becomes the commit message, so it must follow Conventional Commits format.

### PR Size Guidelines

- Prefer small, focused PRs (≤400 lines changed).
- If a feature requires >400 lines, break it into stacked PRs with clearly stated dependencies.
- Refactoring PRs must not mix behaviour changes.

## Code Style

### Python

All Python code must pass `ruff` (linting) and `mypy` (type checking).

```bash
# Check linting
uv run ruff check .

# Auto-fix safe issues
uv run ruff check --fix .

# Format code
uv run ruff format .

# Type check
uv run mypy services/ identity/ security/ --strict
```

#### Style Requirements

- All public functions, methods, and classes must have docstrings.
- All function signatures must have complete type annotations (mypy strict).
- Maximum line length: 100 characters.
- String quotes: double quotes.
- Import ordering: stdlib → third-party → local (enforced by ruff's isort rules).

### Rego (OPA Policies)

- One rule per file where possible.
- Every rule must have a comment block explaining intent, inputs, and outputs.
- Run `opa fmt` on all `.rego` files before committing.
- Policy unit tests are mandatory — place them in `security/tests/` with `_test.rego` suffix.

### Terraform

- Run `terraform fmt -recursive` before committing.
- All resources must have `tags` including `project`, `environment`, and `owner`.
- No hardcoded secrets — use `data "azurerm_key_vault_secret"` or variables with `sensitive = true`.

## Testing Requirements

All contributions must maintain or improve test coverage.

### Coverage Thresholds

| Scope | Minimum Coverage |
|-------|-----------------|
| Unit tests (`tests/unit/`) | 80% line coverage |
| Integration tests (`tests/integration/`) | Key paths covered |
| Security tests (`tests/security/`) | All Bandit HIGH findings resolved |

### Running Tests

```bash
# Full test suite
uv run pytest tests/ -v --cov=services --cov=identity --cov=security --cov-report=term-missing

# Unit tests only (no Docker required)
uv run pytest tests/unit/ -v

# Integration tests (requires running Docker services)
docker-compose up -d
uv run pytest tests/integration/ -v

# Security SAST scan
uv run bandit -r services/ identity/ security/ -ll
```

### Test File Structure

```
tests/
├── unit/
│   ├── test_policy_engine.py
│   ├── test_identity_service.py
│   └── test_posture_scoring.py
├── integration/
│   ├── test_opa_integration.py
│   ├── test_database_access.py
│   └── test_api_endpoints.py
└── security/
    ├── test_input_validation.py
    ├── test_jwt_security.py
    └── test_policy_bypass.py
```

### Test Guidelines

- Use `pytest` with `pytest-asyncio` for async tests.
- Mock external services (Azure OpenAI, Service Bus) in unit tests.
- Integration tests run against real Docker containers — do not mock infrastructure.
- Security tests must attempt known attack patterns (injection, privilege escalation) and assert they are blocked.

## Pre-commit Hooks

Install pre-commit hooks to catch issues before pushing:

```bash
uv run pre-commit install
```

Hooks run automatically on `git commit`. To run them manually:

```bash
uv run pre-commit run --all-files
```

Hooks configured:
- `trailing-whitespace` — removes trailing spaces
- `end-of-file-fixer` — ensures files end with a newline
- `check-yaml` — validates YAML syntax
- `check-toml` — validates TOML syntax
- `ruff` — Python linting
- `ruff-format` — Python formatting
- `mypy` — Python type checking
- `bandit` — Python security scanning

## Documentation

- Update docstrings when changing function signatures or behaviour.
- API changes must be accompanied by updates to the API reference section in `README.md`.
- New environment variables must be added to `.env.example` with descriptive comments.
- Significant changes should include a `CHANGELOG.md` entry under `[Unreleased]`.
