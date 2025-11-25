lint:
	@echo "🔍 Linting"
	@echo "🎨 Auto-formatting"
	uv run black . --exclude 'workspaces|\.venv|frontend|backend/tests'
	uv run isort . --skip-glob 'workspaces/*' --skip-glob '.venv/*'
	uvx ruff check . --exclude workspaces,.venv,frontend,backend/tests
	uv run mypy . --exclude '^(workspaces|\.venv|frontend|backend/tests|ai_scientist/example_code.py)'
	uv run python3 check_inline_imports.py --exclude workspaces,frontend,backend/tests,backend/playground

# Development servers
dev-frontend: gen-api-types
	@echo "🚀 Starting frontend development server..."
	cd frontend && npm run dev

dev-backend: migrate-db gen-api-types
	@echo "🚀 Starting backend development server with DEBUG logging..."
	cd backend && LOG_LEVEL=DEBUG uv run -m uvicorn app.main:app --reload

# OpenAPI export and TS type generation
export-openapi:
	@echo "📝 Exporting OpenAPI schema..."
	cd backend && uv run export_openapi.py > openapi.json

gen-api-types: export-openapi
	@echo "🧬 Generating frontend API types from OpenAPI schema..."
	cd frontend && npx openapi-typescript ../backend/openapi.json --output src/types/api.gen.ts

# Database migrations
migrate-db:
	@echo "📊 Running database migrations..."
	cd backend && uv run migrate.py upgrade
