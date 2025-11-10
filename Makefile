lint:
	@echo "🔍 Linting"
	@echo "🎨 Auto-formatting"
	uv run black . --exclude 'workspaces|\.venv'
	uv run isort . --skip-glob 'workspaces/*' --skip-glob '.venv/*'
	uvx flake8 . --exclude workspaces,.venv
	uv run mypy . --exclude '^(workspaces|\.venv)'
	uv run python3 check_inline_imports.py --exclude workspaces