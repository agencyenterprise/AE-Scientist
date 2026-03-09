# AE-Scientist

A collaborative platform that transforms LLM conversations into structured research ideas and automated AI-driven scientific experiments.

## Project Overview

AE-Scientist consists of three main components that work together to facilitate AI-powered research:

### 🎨 Frontend
**Next.js web application for conversation and project management**
- Import and manage LLM conversations from various providers
- Generate and refine research proposals through interactive AI dialogue
- Track project versions with visual diff viewers
- Search across conversations and projects

📖 [Frontend Documentation](./frontend/README.md)

### 🚀 Server
**FastAPI backend for authentication, data management, and AI orchestration**
- Clerk-baked authentication
- PostgreSQL database for data persistence
- REST API for frontend integration
- LLM integration for idea generation and refinement
- File upload and storage (AWS S3)

📖 [Server Documentation](./server/README.md)

### 🔬 Research Pipeline
**Automated AI scientist for running experiments and generating papers**
- Multi-stage BFTS (Best-First Tree Search) experiment pipeline
- Automatic code generation and experimentation
- Multi-seed evaluation and ablation studies
- LaTeX paper generation with citations
- Support for both local and RunPod GPU execution

📖 [Research Pipeline Documentation](./research_pipeline/README.md)

## Quick Start

### Prerequisites

- **Python 3.12+** (for server and research pipeline)
- **Node.js 20+** (for frontend)
- **PostgreSQL** (for server database)
- **uv** (Python package manager) - [Installation guide](https://github.com/astral-sh/uv)
- **Clerk credentials** (for authentication)

### Installation

Install all dependencies at once:

```bash
make install
```

Or install each component individually:

```bash
make install-server          # Install server dependencies
make install-research        # Install research pipeline dependencies
cd frontend && npm install   # Install frontend dependencies
```

### Configuration

Each component requires its own configuration:

1. **Server**: 
   ```bash
   cp server/env.example server/.env
   # Edit server/.env with your credentials
   ```

2. **Frontend**:
   ```bash
   cp frontend/env.local.example frontend/.env.local
   # Edit frontend/.env.local with API URL
   ```

3. **Research Pipeline**:
   ```bash
   cp research_pipeline/.env.example research_pipeline/.env
   # Edit research_pipeline/.env with API keys
   ```

See individual README files for detailed configuration instructions.

### Development

Start the development servers:

```bash
# Terminal 1 - Database
make migrate-db              # Run database migrations (first time only)

# Terminal 2 - Server
make dev-server              # Start FastAPI server (http://localhost:8000)

# Terminal 3 - Frontend
make dev-frontend            # Start Next.js server (http://localhost:3000)
```

Visit [http://localhost:3000](http://localhost:3000) and sign in with preferred method to get started.

## Available Make Commands

### Installation
```bash
make install                 # Install all dependencies
make install-server          # Install server dependencies
make install-research        # Install research pipeline dependencies
```

### Development
```bash
make dev-server              # Start server development server
make dev-frontend            # Start frontend development server
```

### Linting
```bash
make lint                    # Lint all Python projects
make lint-server             # Lint server only
make lint-research           # Lint research pipeline only
make lint-frontend           # Lint frontend only
```

### Database
```bash
make migrate-db              # Run database migrations
make export-openapi          # Export OpenAPI schema
make gen-api-types           # Generate TypeScript types from OpenAPI schema
```

## Project Structure

```
AE-Scientist/
├── frontend/              # Next.js web application
│   ├── src/              # Source code
│   ├── public/           # Static assets
│   └── README.md         # Frontend documentation
│
├── server/               # FastAPI backend server
│   ├── app/             # Application code
│   ├── database_migrations/  # Alembic migrations
│   └── README.md        # Server documentation
│
├── research_pipeline/   # AI scientist experiment pipeline
│   ├── ai_scientist/    # Core pipeline code
│   └── README.md        # Research pipeline documentation
│
├── linter/              # Shared linting scripts
├── Makefile             # Root makefile (delegates to sub-makefiles)
└── README.md           # This file
```

## Architecture

### Workflow

1. **Conversation Import** (Frontend → Server)
   - User imports LLM conversation via share URL
   - Server fetches and stores conversation in database

2. **Idea Generation** (Server → AI)
   - Server sends conversation to LLM
   - AI generates structured research proposal
   - Multiple refinement iterations possible

3. **Experiment Execution** (Research Pipeline)
   - Research proposal exported to pipeline
   - Automated multi-stage experiments
   - Results collected and papers generated

4. **Results Review** (Server → Frontend)
   - Experimental results stored in database
   - Papers and artifacts accessible via web interface

### Technology Stack

**Frontend:**
- Next.js 15 with React 19
- TypeScript 5
- Tailwind CSS 4
- Clerk auth components (UI)

**Server:**
- FastAPI
- PostgreSQL with Alembic migrations
- SQLAlchemy ORM
- Clerk authentication

**Research Pipeline:**
- PyTorch for ML experiments
- LangChain for LLM orchestration
- Weights & Biases for experiment tracking
- LaTeX for paper generation

## Development Guidelines

### Python Projects (Server & Research Pipeline)

Both Python projects use the same strict linting configuration:

- **black**: Code formatting (100 char line length)
- **isort**: Import sorting
- **ruff**: Fast linting (pycodestyle, pyflakes, unused arguments)
- **mypy**: Strict type checking

Run linting:
```bash
make lint-server        # Lint server
make lint-research      # Lint research pipeline
make lint              # Lint both
```

### Frontend

- **ESLint**: Code linting
- **Prettier**: Code formatting
- **Stylelint**: CSS linting
- **TypeScript**: Type checking

Run linting:
```bash
make lint-frontend     # Lint frontend
```

### Code Style

- Use named arguments in Python functions
- Avoid optional arguments with defaults unless explicitly needed
- Use `pathlib.Path` instead of `os.path`
- Check f-strings actually have variables being replaced
- Keep functions small and focused
- Refactor instead of duplicating code

## Authentication

The application uses Clerk authentication:

1. Users sign in with Clerk account
2. Server validates Clerk token
3. Session cookie stores authentication state
4. All API routes (except auth endpoints) are protected

See [Server Documentation](./server/README.md) for Clerk setup instructions.

## Deployment

### Server (Railway)

The server is configured for Railway deployment:
- `server/railway.toml` defines build configuration
- Environment variables set in Railway dashboard
- Automatic migrations on deployment

### Frontend (Railway/Vercel)

The frontend can be deployed to Railway or Vercel:
- `frontend/railway.toml` for Railway
- Automatic Next.js detection on Vercel
- Configure `NEXT_PUBLIC_API_BASE_URL` to point to production server

### Research Pipeline (RunPod)

For GPU-accelerated experiments:
- Use provided RunPod scripts to create containers
- Configure environment variables in container
- Run experiments via SSH or Jupyter

See [Research Pipeline Documentation](./research_pipeline/README.md) for RunPod setup.

#### RunPod Base Image

The RunPod pipeline uses a pre-baked Docker image defined at `server/app/services/research_pipeline/Dockerfile`. This image installs the LaTeX/PDF toolchain so pods skip long `apt-get` steps.

**Build + push (macOS/Apple Silicon friendly):**
```bash
DOCKER_DEFAULT_PLATFORM=linux/amd64 docker buildx build \
  --platform linux/amd64 \
  -t <dockerhub-username>/runpod_pytorch_texdeps:<tag> \
  -f server/app/services/research_pipeline/Dockerfile \
  --load .
docker push <dockerhub-username>/runpod_pytorch_texdeps:<tag>
```
Setting `DOCKER_DEFAULT_PLATFORM=linux/amd64` ensures you build an x86 image compatible with RunPod’s GPU hosts even when running on Apple Silicon.

**Reference in code:** `server/app/services/research_pipeline/runpod_manager.py` passes the image name to `RunPodCreator.create_pod()`. Update that constant when you publish a new tag so deployments use the latest base image.

## Contributing

### Setup

Follow the [Installation](#installation) section to install all dependencies, configure environment files, and run the development servers.

### Local Database

A local PostgreSQL instance is required. Database migrations live in `server/database_migrations/` and are managed with Alembic. Run pending migrations with:

```bash
make migrate-db
```

### Redis

Redis is used for SSE event streaming and requires Docker. Start it with:

```bash
make redis
```

This runs a Redis container on `localhost:6379`. Stop it with `make redis-stop`.

### API Type Generation

When the server API changes (new endpoints, modified request/response models), regenerate the TypeScript types used by the frontend and research pipeline:

```bash
make gen-api-types
```

This exports the OpenAPI schema from the server and generates typed clients for both the frontend and research pipeline.

### Before Opening a PR

Run linting for all affected components before opening a pull request:

```bash
make lint          # Lint all Python projects (server, research pipeline)
make lint-frontend # Lint frontend (ESLint, Prettier, Stylelint, TypeScript)
```

Both commands must pass with no errors or warnings.

## License

See [LICENSE](./LICENSE) file for details.

## Support

For detailed documentation on each component:
- **Frontend**: [frontend/README.md](./frontend/README.md)
- **Server**: [server/README.md](./server/README.md)
- **Research Pipeline**: [research_pipeline/README.md](./research_pipeline/README.md)
