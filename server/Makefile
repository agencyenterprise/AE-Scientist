# Installation
install:
	@echo "📦 Installing server dependencies..."
	VIRTUAL_ENV= uv sync --inexact
	@echo "📦 Installing ae-paper-review (after sync to avoid removal)..."
	VIRTUAL_ENV= uv pip install -e ../packages/ae-paper-review --quiet

# Linting
lint:
	@echo "🔍 Linting server..."
	@echo "🎨 Auto-formatting server..."
	VIRTUAL_ENV= uv run --no-sync black . --exclude '\.venv'
	VIRTUAL_ENV= uv run --no-sync isort . --skip-glob '.venv/*'
	VIRTUAL_ENV= uv run --no-sync ruff check . --exclude .venv
	VIRTUAL_ENV= uv run --no-sync mypy . --exclude '^(\.venv|playground)'
	VIRTUAL_ENV= uv run --no-sync pyright --project pyproject.toml
	VIRTUAL_ENV= uv run --no-sync vulture app/ --exclude .venv --min-confidence 80
	VIRTUAL_ENV= uv run --no-sync python ../linter/check_inline_imports.py --target-dir . --exclude playground
	@echo "✅ Linting complete"

# Development server
dev: migrate gen-api-types
	@echo "🚀 Starting server development server with DEBUG logging..."
	VIRTUAL_ENV= LOG_LEVEL=DEBUG uv run -m uvicorn app.main:app --reload --reload-dir . --reload-dir ../packages/ae-paper-review

# OpenAPI export
export-openapi:
	@echo "📝 Exporting OpenAPI schema..."
	VIRTUAL_ENV= uv run --no-sync export_openapi.py > openapi.json

# Fake RunPod server for local validation
# Usage: make fake-runpod [SPEED=N] where N is the speed multiplier (default: 1)
SPEED ?= 1
fake-runpod:
	@echo "🎭 Starting fake RunPod server with auto-reload (speed=$(SPEED)x)..."
	VIRTUAL_ENV= PYTHONPATH=../research_pipeline:..:$(PYTHONPATH) uv run watchfiles "python -m app.services.research_pipeline.fake_runpod.runner --speed $(SPEED)" app/services/research_pipeline/fake_runpod

# Generate API types for frontend
gen-api-types: export-openapi
	@echo "🧬 Generating frontend API types from OpenAPI schema..."
	cd ../frontend && npx openapi-typescript ../server/openapi.json --output src/types/api.gen.ts

# Database migrations
migrate:
	@echo "📊 Running database migrations..."
	VIRTUAL_ENV= uv run migrate.py upgrade

.PHONY: install lint dev export-openapi gen-api-types migrate fake-runpod

