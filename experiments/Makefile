# Installation
install:
	@echo "📦 Installing experiments dependencies..."
	VIRTUAL_ENV= uv sync --inexact

# Linting
lint:
	@echo "🔍 Linting experiments..."
	@echo "🎨 Auto-formatting..."
	VIRTUAL_ENV= uv run --no-sync black . --exclude '\.venv'
	VIRTUAL_ENV= uv run --no-sync isort . --skip-glob '.venv/*'
	VIRTUAL_ENV= uv run --no-sync ruff check . --exclude .venv
	VIRTUAL_ENV= uv run --no-sync mypy . --exclude '^(\.venv)'
	VIRTUAL_ENV= uv run --no-sync pyright --project pyproject.toml
	VIRTUAL_ENV= uv run --no-sync vulture paper_sourcing/ benchmark/ --exclude .venv --min-confidence 80
	VIRTUAL_ENV= uv run --no-sync python ../linter/check_inline_imports.py --target-dir .
	@echo "✅ Linting complete"

.PHONY: install lint
