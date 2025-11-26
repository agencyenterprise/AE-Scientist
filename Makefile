# Installation targets
install-research:
	$(MAKE) -C research_pipeline install

install-server:
	$(MAKE) -C server install

install: install-research install-server
	@echo "✅ All dependencies installed"

# Linting targets
lint-research:
	$(MAKE) -C research_pipeline lint

lint-server:
	$(MAKE) -C server lint

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

dev-server:
	$(MAKE) -C server dev

# OpenAPI export and TS type generation
export-openapi:
	$(MAKE) -C server export-openapi

gen-api-types:
	$(MAKE) -C server gen-api-types

# Database migrations
migrate-db:
	$(MAKE) -C server migrate

.PHONY: install-research install-server install lint-research lint-server lint lint-frontend dev-frontend dev-server export-openapi gen-api-types migrate-db
