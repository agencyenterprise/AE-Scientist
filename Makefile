# Installation targets
install-ae-paper-review:
	$(MAKE) -C packages/ae-paper-review install

install-research:
	$(MAKE) -C research_pipeline install

install-server:
	$(MAKE) -C server install

install: install-ae-paper-review install-research install-server
	@echo "All dependencies installed"

# Linting targets
lint-ae-paper-review:
	$(MAKE) -C packages/ae-paper-review lint

lint-research:
	$(MAKE) -C research_pipeline lint

lint-server:
	$(MAKE) -C server lint

lint: lint-ae-paper-review lint-research lint-server
	@echo "All linting complete"

lint-frontend:
	@echo "Linting frontend..."
	cd frontend && npm run format:check || (echo "Formatting frontend sources..." && npm run format && npm run format:check)
	cd frontend && npm run lint -- --max-warnings 0
	cd frontend && npm run style:check
	@echo "Type checking frontend..."
	cd frontend && npx tsc --noEmit

# Development servers
dev-frontend:
	@echo "Starting frontend development server..."
	cd frontend && npm run dev

dev-server:
	$(MAKE) -C server dev

# Usage: make fake-runpod [SPEED=N] [SIMULATE_FAILURE=1]
#   SPEED=N - speed multiplier (default: 1)
#   SIMULATE_FAILURE=1 - simulate a system failure after the first LLM cost event
SPEED ?= 1
SIMULATE_FAILURE ?=
fake-runpod:
	$(MAKE) -C server fake-runpod SPEED=$(SPEED) SIMULATE_FAILURE=$(SIMULATE_FAILURE)

# OpenAPI export and type generation
export-openapi:
	$(MAKE) -C server export-openapi

gen-api-types:
	$(MAKE) -C server gen-api-types
	$(MAKE) -C research_pipeline gen-api-types

# Database migrations
migrate-db:
	$(MAKE) -C server migrate

# Redis for SSE event streaming
redis:
	@echo "Starting Redis container..."
	@docker run -d --name ae-scientist-redis -p 6379:6379 redis:7-alpine || \
		(docker start ae-scientist-redis 2>/dev/null && echo "Redis container already exists, starting it...")
	@echo "Redis is running on localhost:6379"

redis-stop:
	@echo "Stopping Redis container..."
	@docker stop ae-scientist-redis 2>/dev/null || true
	@echo "Redis stopped"

redis-rm:
	@echo "Removing Redis container..."
	@docker stop ae-scientist-redis 2>/dev/null || true
	@docker rm ae-scientist-redis 2>/dev/null || true
	@echo "Redis container removed"

.PHONY: install-ae-paper-review install-research install-server install lint-ae-paper-review lint-research lint-server lint lint-frontend dev-frontend dev-server export-openapi gen-api-types migrate-db fake-runpod redis redis-stop redis-rm
