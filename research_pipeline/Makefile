# Installation
install:
	@echo "📦 Installing research_pipeline dependencies..."
	VIRTUAL_ENV= uv sync --inexact
	@echo "📦 Installing ae-paper-review (after sync to avoid removal)..."
	VIRTUAL_ENV= uv pip install -e ../packages/ae-paper-review --quiet

# Generate Python types from OpenAPI spec
gen-api-types:
	@echo "🧬 Generating Python API types from OpenAPI schema..."
	$(MAKE) -C ../server export-openapi
	@# Add venv bin to PATH so datamodel-codegen can find ruff
	PATH="$(CURDIR)/.venv/bin:$$PATH" VIRTUAL_ENV= uv run datamodel-codegen \
		--input ../server/openapi.json \
		--output ai_scientist/api_types.py \
		--output-model-type pydantic_v2.BaseModel \
		--target-python-version 3.12 \
		--use-annotated \
		--field-constraints \
		--input-file-type openapi \
		--use-double-quotes \
		--collapse-root-models \
		--use-default-kwarg \
		--enum-field-as-literal one \
		--formatters ruff-format ruff-check
	@# Add mypy ignore directive and remove timestamp (to avoid spurious diffs)
	@grep -v '#   timestamp:' ai_scientist/api_types.py > ai_scientist/api_types.py.tmp && mv ai_scientist/api_types.py.tmp ai_scientist/api_types.py
	@echo '# mypy: ignore-errors' | cat - ai_scientist/api_types.py > ai_scientist/api_types.py.tmp && mv ai_scientist/api_types.py.tmp ai_scientist/api_types.py
	@echo "✅ API types generated at ai_scientist/api_types.py"

# Linting
lint:
	@echo "🔍 Linting research_pipeline..."
	@echo "🎨 Auto-formatting research_pipeline..."
	VIRTUAL_ENV= uv run --no-sync black . --exclude 'workspaces|\.venv'
	VIRTUAL_ENV= uv run --no-sync isort . --skip-glob 'workspaces/*' --skip-glob '.venv/*'
	VIRTUAL_ENV= uv run --no-sync ruff check . --exclude workspaces,.venv,ai_scientist/example_code.py
	VIRTUAL_ENV= uv run --no-sync mypy . --exclude '^(workspaces|\.venv|ai_scientist/example_code.py|ai_scientist/api_types.py)'
	VIRTUAL_ENV= uv run --no-sync pyright --project pyproject.toml
	VIRTUAL_ENV= uv run --no-sync python ../linter/check_inline_imports.py --target-dir . --exclude workspaces
	@echo "✅ Linting complete"

.PHONY: install lint gen-api-types

