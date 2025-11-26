# Installation
install:
	@echo "📦 Installing server dependencies..."
	uv sync

# Linting
lint:
	@echo "🔍 Linting server..."
	@echo "🎨 Auto-formatting server..."
	VIRTUAL_ENV= uv run black . --exclude '\.venv|tests'
	VIRTUAL_ENV= uv run isort . --skip-glob '.venv/*'
	VIRTUAL_ENV= uv run ruff check . --exclude .venv,tests
	VIRTUAL_ENV= uv run mypy . --exclude '^(\.venv|tests|playground)'
	VIRTUAL_ENV= uv run python ../linter/check_inline_imports.py --target-dir . --exclude tests,playground
	@echo "✅ Linting complete"

# Development server
dev: migrate gen-api-types
	@echo "🚀 Starting server development server with DEBUG logging..."
	VIRTUAL_ENV= LOG_LEVEL=DEBUG uv run -m uvicorn app.main:app --reload

# OpenAPI export
export-openapi:
	@echo "📝 Exporting OpenAPI schema..."
	VIRTUAL_ENV= uv run export_openapi.py > openapi.json

# Generate API types for frontend
gen-api-types: export-openapi
	@echo "🧬 Generating frontend API types from OpenAPI schema..."
	cd ../frontend && npx openapi-typescript ../server/openapi.json --output src/types/api.gen.ts

# Database migrations
migrate:
	@echo "📊 Running database migrations..."
	VIRTUAL_ENV= uv run migrate.py upgrade

.PHONY: install lint dev export-openapi gen-api-types migrate

