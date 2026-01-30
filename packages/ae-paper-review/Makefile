# Installation
install:
	@echo "📦 Installing ae-paper-review dependencies..."
	@[ -d .venv ] || uv venv --quiet
	uv pip install -e ".[dev]"

# Linting
lint:
	@echo "🔍 Linting ae-paper-review..."
	@echo "🎨 Auto-formatting ae-paper-review..."
	VIRTUAL_ENV= uv run black src --exclude '\.venv'
	VIRTUAL_ENV= uv run isort src --skip-glob '.venv/*'
	VIRTUAL_ENV= uv run ruff check src --exclude .venv
	VIRTUAL_ENV= uv run mypy src --exclude '^\.venv'
	VIRTUAL_ENV= uv run pyright src
	@echo "✅ Linting complete"

# Testing
test:
	@echo "🧪 Running ae-paper-review tests..."
	VIRTUAL_ENV= uv run python -m pytest tests
	@echo "✅ Tests complete"

.PHONY: install lint test
