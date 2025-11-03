lint:
	@echo "🔍 Linting"
	@echo "🎨 Auto-formatting"
	uv run black .
	uv run isort .
	uvx flake8 .
	uv run mypy .