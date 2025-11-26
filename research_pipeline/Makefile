# Installation
install:
	@echo "📦 Installing research_pipeline dependencies..."
	uv sync

# Linting
lint:
	@echo "🔍 Linting research_pipeline..."
	@echo "🎨 Auto-formatting research_pipeline..."
	VIRTUAL_ENV= uv run black . --exclude 'workspaces|\.venv'
	VIRTUAL_ENV= uv run isort . --skip-glob 'workspaces/*' --skip-glob '.venv/*'
	VIRTUAL_ENV= uv run ruff check . --exclude workspaces,.venv
	VIRTUAL_ENV= uv run mypy . --exclude '^(workspaces|\.venv|ai_scientist/example_code.py)'
	VIRTUAL_ENV= uv run python ../linter/check_inline_imports.py --target-dir . --exclude workspaces
	@echo "✅ Linting complete"

.PHONY: install lint

