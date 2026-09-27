VERSION := $(shell cat VERSION)
REGISTRY ?= myregistry.azurecr.io
IMAGE_NAME := agentic-zero-trust/api
FULL_IMAGE := $(REGISTRY)/$(IMAGE_NAME):$(VERSION)

.PHONY: install dev test test-unit test-integration test-security lint format \
        build push terraform-init terraform-plan terraform-apply \
        docker-up docker-down helm-lint clean

## install: Install all Python dependencies using uv
install:
	uv sync --all-extras

## dev: Start the full stack in development mode (with overrides)
dev:
	docker-compose -f docker-compose.yml -f docker-compose.override.yml up -d

## test: Run all tests with coverage report
test:
	uv run pytest tests/ -v --cov=services --cov-report=html --cov-report=term-missing

## test-unit: Run unit tests only
test-unit:
	uv run pytest tests/unit/ -v --cov=services --cov-report=term-missing

## test-integration: Run integration tests (requires running services)
test-integration:
	uv run pytest tests/integration/ -v --timeout=60 --cov=services --cov-report=term-missing

## test-security: Run security-focused tests with bandit and safety
test-security:
	uv run bandit -r services/ -ll -f txt
	uv run safety check --full-report
	uv run pytest tests/security/ -v

## lint: Run ruff linting and mypy type checking
lint:
	uv run ruff check . --output-format=text
	uv run mypy services/ --ignore-missing-imports --strict

## format: Auto-format code with ruff
format:
	uv run ruff format .
	uv run ruff check --fix .

## build: Build the API Docker image
build:
	docker build \
		--build-arg VERSION=$(VERSION) \
		-t $(IMAGE_NAME):$(VERSION) \
		-t $(IMAGE_NAME):latest \
		-f services/api/Dockerfile \
		.

## push: Push Docker images to the container registry
push:
	docker tag $(IMAGE_NAME):$(VERSION) $(FULL_IMAGE)
	docker tag $(IMAGE_NAME):latest $(REGISTRY)/$(IMAGE_NAME):latest
	docker push $(FULL_IMAGE)
	docker push $(REGISTRY)/$(IMAGE_NAME):latest

## terraform-init: Initialize Terraform working directory
terraform-init:
	cd infra/azure && terraform init

## terraform-plan: Generate and show a Terraform execution plan
terraform-plan:
	cd infra/azure && terraform plan -out=tfplan

## terraform-apply: Apply the most recent Terraform plan
terraform-apply:
	cd infra/azure && terraform apply tfplan

## docker-up: Start all services with docker-compose
docker-up:
	docker-compose up -d

## docker-down: Stop and remove all docker-compose containers
docker-down:
	docker-compose down

## helm-lint: Lint the Helm chart
helm-lint:
	helm lint deploy/helm/agentic-zero-trust/

## clean: Remove build artifacts, caches, and temporary files
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	find . -name "*.pyo" -delete 2>/dev/null || true
	find . -name "*.pyd" -delete 2>/dev/null || true
	find . -name ".pytest_cache" -type d -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.egg-info" -type d -exec rm -rf {} + 2>/dev/null || true
	rm -rf .coverage htmlcov/ dist/ build/ .mypy_cache/ .ruff_cache/
	rm -f bandit-report.json safety-report.txt

## help: Show this help message
help:
	@echo "Available targets:"
	@grep -E '^## ' Makefile | sed 's/## /  /'
