# AE Paper Review - Root Makefile

.PHONY: install dev dev-backend dev-frontend lint migrate gen-api-types build

# Install all dependencies
install:
	@echo "Installing backend dependencies..."
	cd backend && make install
	@echo "Installing frontend dependencies..."
	cd frontend && npm install

# Run database migrations
migrate:
	cd backend && make migrate

# Run both backend and frontend in development mode
dev:
	@echo "Starting development servers..."
	@echo "Backend: http://localhost:8000"
	@echo "Frontend: http://localhost:3000"
	@make -j2 dev-backend dev-frontend

dev-backend:
	cd backend && make dev

dev-frontend:
	cd frontend && npm run dev

# Lint both backend and frontend
lint:
	@echo "Linting backend..."
	cd backend && make lint
	@echo "Linting frontend..."
	cd frontend && npm run format:check || (echo "Formatting frontend sources..." && npm run format && npm run format:check)
	cd frontend && npm run lint -- --max-warnings 0
	cd frontend && npm run style:check
	@echo "Type checking frontend..."
	cd frontend && npx tsc --noEmit

# Generate API types for frontend
gen-api-types:
	cd backend && make gen-api-types

# Build for production
build:
	@echo "Building backend..."
	cd backend && uv sync
	@echo "Building frontend..."
	cd frontend && npm run build
