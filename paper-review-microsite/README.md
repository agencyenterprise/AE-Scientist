# AE Paper Review

A standalone microsite for AI-powered academic paper reviews. Upload a PDF and get comprehensive analysis including strengths, weaknesses, scores, and recommendations.

## Features

- **AI Paper Review**: Uses the `ae-paper-review` package for LLM-based paper analysis
- **Multiple Models**: Support for Anthropic (Claude), OpenAI (GPT-4), and xAI (Grok)
- **Ensemble Reviews**: Configure multiple review passes for more thorough analysis
- **Reflection Rounds**: Iterative refinement of review quality
- **Real-time Progress**: Live progress updates during review processing
- **Review History**: Access all past reviews with full details
- **Clerk Authentication**: Secure user authentication via Clerk
- **Free/Unlimited**: No billing or credit system

## Tech Stack

**Backend:**
- FastAPI with async support
- PostgreSQL with psycopg3
- Alembic for migrations
- S3 for PDF storage
- Clerk JWT verification

**Frontend:**
- Next.js 16 (App Router)
- React 19
- TanStack Query
- Tailwind CSS v4
- Clerk for auth UI

## Prerequisites

- Python 3.12+
- Node.js 20+
- PostgreSQL 14+
- AWS S3 bucket
- Clerk account

## Setup

### 1. Clone and Install

```bash
cd paper-review-microsite
make install
```

### 2. Configure Environment

**Backend** (`backend/.env`):
```bash
cp backend/.env.example backend/.env
# Edit backend/.env with your values
```

**Frontend** (`frontend/.env.local`):
```bash
cp frontend/.env.local.example frontend/.env.local
# Edit frontend/.env.local with your values
```

### 3. Create Database

```bash
createdb paper_review_microsite
```

### 4. Run Migrations

```bash
make migrate
```

### 5. Start Development Servers

```bash
make dev
```

This starts:
- Backend: http://localhost:8000
- Frontend: http://localhost:3000

## Environment Variables

### Backend

| Variable | Description | Required |
|----------|-------------|----------|
| `DATABASE_URL` | PostgreSQL connection string | Yes |
| `CLERK_SECRET_KEY` | Clerk secret key | Yes |
| `CLERK_PUBLISHABLE_KEY` | Clerk publishable key | Yes |
| `AWS_ACCESS_KEY_ID` | AWS access key | Yes |
| `AWS_SECRET_ACCESS_KEY` | AWS secret key | Yes |
| `AWS_REGION` | AWS region | Yes |
| `AWS_S3_BUCKET_NAME` | S3 bucket for PDFs | Yes |
| `ANTHROPIC_API_KEY` | Anthropic API key | No* |
| `OPENAI_API_KEY` | OpenAI API key | No* |
| `XAI_API_KEY` | xAI API key | No* |
| `FRONTEND_URL` | Frontend URL for CORS | Yes |
| `CORS_ORIGINS` | Allowed CORS origins | Yes |

*At least one LLM API key is required.

### Frontend

| Variable | Description | Required |
|----------|-------------|----------|
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | Clerk publishable key | Yes |
| `CLERK_SECRET_KEY` | Clerk secret key | Yes |
| `NEXT_PUBLIC_API_BASE_URL` | Backend API URL | Yes |

## Available Commands

### Root

```bash
make install        # Install all dependencies
make dev            # Run both servers in development
make dev-backend    # Run backend only
make dev-frontend   # Run frontend only
make lint           # Lint both projects
make migrate        # Run database migrations
make gen-api-types  # Generate TypeScript types from OpenAPI
make build          # Build for production
```

### Backend

```bash
cd backend
make install        # Install Python dependencies
make dev            # Run development server
make lint           # Run linters (black, isort, ruff, mypy, pyright, vulture)
make migrate        # Run Alembic migrations
make export-openapi # Export OpenAPI schema
```

### Frontend

```bash
cd frontend
npm run dev         # Run development server
npm run build       # Build for production
npm run lint        # Run ESLint
npm run gen:api-types  # Generate types from running server
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/auth/clerk-session` | Exchange Clerk JWT for session token |
| GET | `/api/auth/me` | Get current user |
| GET | `/api/auth/status` | Check authentication status |
| POST | `/api/auth/logout` | Invalidate session |
| GET | `/api/models` | List available LLM models |
| POST | `/api/paper-reviews` | Submit paper for review |
| GET | `/api/paper-reviews` | List user's reviews |
| GET | `/api/paper-reviews/pending` | Get in-progress reviews |
| GET | `/api/paper-reviews/{id}` | Get review details |
| GET | `/api/paper-reviews/{id}/download` | Get PDF download URL |

## Project Structure

```
paper-review-microsite/
├── Makefile                    # Root commands
├── README.md
├── backend/
│   ├── Makefile
│   ├── pyproject.toml
│   ├── alembic.ini
│   ├── migrate.py
│   ├── export_openapi.py
│   ├── database_migrations/
│   │   └── versions/
│   └── app/
│       ├── main.py             # FastAPI app
│       ├── config.py           # Settings
│       ├── routes.py           # Router
│       ├── api/                # Endpoints
│       ├── auth/               # Token utilities
│       ├── middleware/         # Auth middleware
│       ├── models/             # Pydantic models
│       └── services/           # Business logic
│           └── database/       # DB operations
└── frontend/
    ├── package.json
    ├── next.config.ts
    ├── tsconfig.json
    └── src/
        ├── app/                # Next.js pages
        ├── features/
        │   └── paper-review/   # Review components
        ├── shared/             # Utilities & UI
        └── types/              # Generated types
```

## Development Notes

- The backend depends on `ae-paper-review` package (editable install from `../../packages/ae-paper-review`)
- Frontend TypeScript types are generated from the backend OpenAPI schema
- Reviews are processed asynchronously with real-time progress updates
- PDFs are stored in S3 with signed download URLs
