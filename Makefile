# Installation targets
install-research:
	@echo "📦 Installing research_pipeline dependencies..."
	cd research_pipeline && uv sync

install-server:
	@echo "📦 Installing server dependencies..."
	cd server && uv sync

install: install-research install-server
	@echo "✅ All dependencies installed"

# Linting targets
lint-research:
	@echo "🔍 Linting research_pipeline..."
	@echo "🎨 Auto-formatting research_pipeline..."
	cd research_pipeline && uv run black . --exclude 'workspaces|\.venv'
	cd research_pipeline && uv run isort . --skip-glob 'workspaces/*' --skip-glob '.venv/*'
	cd research_pipeline && uv run ruff check . --exclude workspaces,.venv
	cd research_pipeline && uv run mypy . --exclude '^(workspaces|\.venv|ai_scientist/example_code.py)'
	uv run --directory research_pipeline python ../linter/check_inline_imports.py --target-dir research_pipeline --exclude workspaces

lint-server:
	@echo "🔍 Linting server..."
	@echo "🎨 Auto-formatting server..."
	cd server && uv run black . --exclude '\.venv|tests'
	cd server && uv run isort . --skip-glob '.venv/*'
	cd server && uv run ruff check . --exclude .venv,tests
	cd server && uv run mypy . --exclude '^(\.venv|tests|playground)'
	uv run --directory server python ../linter/check_inline_imports.py --target-dir server --exclude tests,playground

lint: lint-research lint-server
	@echo "✅ All linting complete"

lint-frontend:
	@echo "🔍 Linting frontend..."
	@echo "🎨 Auto-formatting frontend..."
	cd frontend && npm run format
	cd frontend && npm run lint
	cd frontend && npm run style
	@echo "🔍 Type checking frontend..."
	cd frontend && npx tsc --noEmit

# Development servers
dev-frontend: gen-api-types
	@echo "🚀 Starting frontend development server..."
	cd frontend && npm run dev

dev-server: migrate-db gen-api-types
	@echo "🚀 Starting server development server with DEBUG logging..."
	cd server && LOG_LEVEL=DEBUG uv run -m uvicorn app.main:app --reload

# OpenAPI export and TS type generation
export-openapi:
	@echo "📝 Exporting OpenAPI schema..."
	cd server && uv run export_openapi.py > openapi.json

gen-api-types: export-openapi
	@echo "🧬 Generating frontend API types from OpenAPI schema..."
	cd frontend && npx openapi-typescript ../server/openapi.json --output src/types/api.gen.ts

# Database migrations
migrate-db:
	@echo "📊 Running database migrations..."
	cd server && uv run migrate.py upgrade
