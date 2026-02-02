# Installation
install:
	@echo "📦 Installing ae-paper-review dependencies..."
	@[ -d .venv ] || uv venv --quiet
	uv pip install -e ".[dev]"

# Linting
lint:
	@echo "🔍 Linting ae-paper-review..."
	@echo "🎨 Auto-formatting ae-paper-review..."
	VIRTUAL_ENV= uv run --no-sync black src --exclude '\.venv'
	VIRTUAL_ENV= uv run --no-sync isort src --skip-glob '.venv/*'
	VIRTUAL_ENV= uv run --no-sync ruff check src --exclude .venv
	VIRTUAL_ENV= uv run --no-sync mypy src --exclude '^\.venv'
	VIRTUAL_ENV= uv run --no-sync pyright src
	VIRTUAL_ENV= uv run --no-sync vulture src --min-confidence 80
	@echo "✅ Linting complete"


.PHONY: install lint
