# Server Architecture

## Related Documentation
- [README.md](../README.md) - Documentation index
- [Project Architecture](project_architecture.md) - Overall system architecture
- [Frontend Architecture](frontend_architecture.md) - Next.js frontend

---

## 1. Overview

The server is a FastAPI application providing REST APIs for conversation management, AI-powered research idea generation, and real-time chat with multiple LLM providers.

### Tech Stack

| Technology | Purpose |
|------------|---------|
| FastAPI | Async Python web framework |
| PostgreSQL | Primary database |
| Alembic | Database migrations |
| psycopg2 | PostgreSQL driver |
| LangChain | LLM abstraction layer |
| AsyncOpenAI/AsyncAnthropic | LLM API clients |

### Key Capabilities
- Multi-provider LLM integration (OpenAI, Anthropic, Grok)
- Conversation import from ChatGPT, Claude, Grok, BranchPrompt URLs
- Manual idea seed creation from title/hypothesis
- AI-powered research idea generation with structured output
- Real-time streaming responses with Server-Sent Events (SSE)
- Google OAuth authentication
- S3 file storage with processing

---

## 2. Project Structure

```
server/
├── app/
│   ├── main.py              # FastAPI app initialization
│   ├── config.py            # Settings management
│   ├── routes.py            # Main router aggregator
│   ├── prompt_types.py      # Prompt type enums
│   │
│   ├── api/                 # API route handlers
│   │   ├── auth.py          # Google OAuth authentication
│   │   ├── chat.py          # Chat endpoints
│   │   ├── chat_stream.py   # Streaming chat (SSE)
│   │   ├── conversations.py # Conversation import & management
│   │   ├── files.py         # File upload/download
│   │   ├── ideas.py         # Research idea endpoints
│   │   ├── llm_defaults.py  # LLM provider configuration
│   │   └── llm_prompts.py   # Custom prompt management
│   │
│   ├── middleware/
│   │   └── auth.py          # Authentication middleware
│   │
│   ├── models/              # Pydantic models
│   │   ├── auth.py          # User, session, OAuth models
│   │   ├── chat.py          # Chat request/response models
│   │   ├── conversations.py # Conversation import models
│   │   ├── ideas.py         # Idea generation models
│   │   ├── imported_conversation_summary.py
│   │   └── llm_prompts.py   # LLM configuration models
│   │
│   └── services/            # Business logic
│       ├── base_llm_service.py      # Abstract LLM interface
│       ├── openai_service.py        # OpenAI integration
│       ├── anthropic_service.py     # Anthropic/Claude integration
│       ├── grok_service.py          # xAI Grok integration
│       ├── langchain_llm_service.py # LangChain wrapper
│       ├── auth_service.py          # Google OAuth
│       ├── s3_service.py            # AWS S3 file storage
│       ├── pdf_service.py           # PDF processing
│       ├── summarizer_service.py    # Text summarization
│       ├── mem0_service.py          # Memory/context service
│       ├── parser_router.py         # Routes to correct parser
│       ├── prompts.py               # Prompt templates
│       ├── chat_models.py           # Stream event types
│       │
│       ├── scraper/                 # Conversation parsers
│       │   ├── chat_gpt_parser.py   # ChatGPT URL parsing
│       │   ├── claude_parser.py     # Claude URL parsing
│       │   ├── grok_parser.py       # Grok URL parsing
│       │   ├── branchprompt_parser.py
│       │   └── errors.py            # Parser exceptions
│       │
│       └── database/                # Database access layer
│           ├── base.py              # PostgreSQL connection
│           ├── users.py             # User CRUD
│           ├── conversations.py     # Conversation queries
│           ├── ideas.py             # Idea storage & versioning
│           ├── chat_messages.py     # Chat message storage
│           ├── chat_summaries.py
│           ├── file_attachments.py
│           ├── llm_defaults.py
│           ├── memories.py
│           ├── imported_conversation_summaries.py
│           └── prompts.py
│
├── database_migrations/     # Alembic migrations
│   ├── versions/
│   │   ├── 0001_initial_schema.py
│   │   ├── 0002_drop_service_keys.py
│   │   └── 0003_manual_seed_columns.py
│   └── env.py
│
├── tests/                   # Test suite
├── playground/              # Development scripts
├── pyproject.toml           # Python dependencies (uv)
├── Dockerfile
├── docker-compose.yml       # PostgreSQL setup
├── Makefile                 # Development tasks
├── migrate.py               # Migration CLI helper
└── alembic.ini
```

---

## 3. API Routes & Endpoints

All routes prefixed with `/api`.

### Authentication (`/api/auth`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/login` | Initiate Google OAuth flow |
| GET | `/callback` | OAuth callback, sets session cookie |
| GET | `/me` | Get current user info |
| GET | `/status` | Check authentication status (public) |
| POST | `/logout` | Clear session |

### Conversations (`/api/conversations`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/import` | Import conversation from URL (streaming) |
| POST | `/import/manual` | Create idea from manual title/hypothesis (streaming) |
| GET | `/` | List all conversations (paginated) |
| GET | `/{id}` | Get conversation details |
| DELETE | `/{id}` | Delete conversation |
| PATCH | `/{id}` | Update conversation title |
| GET | `/{id}/imported_chat_summary` | Get conversation summary |
| PATCH | `/{id}/summary` | Update conversation summary |

### Ideas (`/api/conversations`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/{id}/idea` | Get generated research idea |
| PATCH | `/{id}/idea` | Update idea manually |
| GET | `/{id}/idea/versions` | Get all idea versions |
| POST | `/{id}/idea/versions/{version_id}/activate` | Restore previous version |

### Chat (`/api/chat_stream`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/stream` | Stream chat with LLM (SSE) |

### Files (`/api/files`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/{id}/upload` | Upload file attachment |
| GET | `/{id}/download` | Download file (signed S3 URL) |

### LLM Configuration (`/api/llm-prompts`, `/api/llm-defaults`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/llm-prompts/{type}` | Get active prompt |
| GET | `/llm-prompts/{type}/default` | Get default prompt |
| POST | `/llm-prompts/{type}` | Create/update custom prompt |
| DELETE | `/llm-prompts/{type}` | Revert to default |
| GET | `/llm-defaults/providers` | Get available providers/models |
| GET | `/llm-defaults/{type}` | Get default LLM for prompt type |
| PUT | `/llm-defaults/{type}` | Update default LLM |

---

## 4. Service Layer

### LLM Services

All LLM services inherit from `BaseLLMService` providing common functionality:
- Token estimation
- Text chunking
- Map-reduce for long documents
- Document summarization

#### LangChain LLM Service

The `LangChainLLMService` provides a unified interface across all LLM providers using LangChain:
- Supports OpenAI, Anthropic, Groq providers
- Structured output with JSON schema
- Streaming generation
- Idea generation from conversations or manual seeds

#### OpenAI Service

**Supported Models:**
| Model | Context Window | Capabilities |
|-------|---------------|--------------|
| gpt-4o | 128K | Vision, streaming |
| gpt-4o-mini | 128K | Vision, streaming |
| gpt-4-turbo | 128K | Vision, streaming |
| gpt-4.1 | 1M | Vision, PDF |
| gpt-4.1-mini | 1M | Vision, PDF |
| o1, o3, gpt-5 | Various | Advanced reasoning |

#### Anthropic (Claude) Service

**Supported Models:**
| Model | Context Window |
|-------|---------------|
| claude-opus-4 | 200K |
| claude-sonnet-4 | 200K |
| claude-3.5-haiku | 200K |
| claude-3.7-sonnet | 200K |

#### Grok Service

**Supported Models:**
| Model | Context Window |
|-------|---------------|
| grok-4 | 256K |
| grok-3 | 131K |
| grok-3-mini | 131K |
| grok-code-fast-1 | 131K |

Uses OpenAI-compatible API at `https://api.x.ai/v1`

### Authentication Service

- Google OAuth 2.0 integration
- Session management (configurable expiration)

### S3 Service

- File validation (magic numbers, MIME types)
- Allowed: JPEG, PNG, GIF, WebP, SVG, PDF, text
- Max size: 10MB
- Signed URL generation
- Folder structure: `conversations/{id}/files/{filename}`

### Summarizer Service

- External metacognition API integration
- Background polling (5s intervals, 100min timeout)
- Supports imported chat summaries
- Callback-based completion handling

### Parser Services

**ParserRouterService** routes URLs to the correct parser:

| Parser | URL Pattern |
|--------|-------------|
| ChatGPTParserService | `chatgpt.com/share/{uuid}` |
| ClaudeParserService | `claude.ai/share/{uuid}` |
| GrokParserService | `grok.com/share/...` |
| BranchPromptParserService | `v2.branchprompt.com/conversation/{24-hex}` |

---

## 5. Database Schema

### Core Tables

#### `users`
```sql
id              SERIAL PRIMARY KEY
google_id       TEXT UNIQUE NOT NULL
email           TEXT UNIQUE NOT NULL
name            TEXT NOT NULL
is_active       BOOLEAN DEFAULT TRUE
created_at      TIMESTAMPTZ
updated_at      TIMESTAMPTZ
```

#### `user_sessions`
```sql
id              SERIAL PRIMARY KEY
user_id         FK → users
session_token   TEXT UNIQUE
expires_at      TIMESTAMPTZ
created_at      TIMESTAMPTZ
```

#### `conversations`
```sql
id              SERIAL PRIMARY KEY
url             TEXT NOT NULL (indexed)
title           TEXT NOT NULL (full-text indexed)
import_date     TIMESTAMPTZ DEFAULT NOW()
imported_chat   JSONB NOT NULL          -- Array of messages
imported_by_user_id  FK → users
manual_title    TEXT                    -- For manual seed
manual_hypothesis TEXT                  -- For manual seed
has_images      BOOLEAN
has_pdfs        BOOLEAN
created_at      TIMESTAMPTZ
updated_at      TIMESTAMPTZ
```

#### `ideas`
```sql
id              SERIAL PRIMARY KEY
conversation_id FK → conversations CASCADE
active_idea_version_id FK → idea_versions SET NULL
created_by_user_id FK → users
created_at      TIMESTAMPTZ
updated_at      TIMESTAMPTZ
```

#### `idea_versions`
```sql
id              SERIAL PRIMARY KEY
idea_id         FK → ideas CASCADE
title           TEXT NOT NULL
short_hypothesis TEXT NOT NULL
related_work    TEXT NOT NULL
abstract        TEXT NOT NULL
experiments     JSONB NOT NULL          -- Array of strings
expected_outcome TEXT NOT NULL
risk_factors_and_limitations JSONB NOT NULL  -- Array of strings
is_manual_edit  BOOLEAN DEFAULT FALSE
version_number  INTEGER NOT NULL
created_by_user_id FK → users
created_at      TIMESTAMPTZ
```

#### `chat_messages`
```sql
id              SERIAL PRIMARY KEY
idea_id         FK → ideas CASCADE
role            TEXT CHECK IN ('user', 'assistant')
content         TEXT NOT NULL
sequence_number INTEGER NOT NULL
sent_by_user_id FK → users
created_at      TIMESTAMPTZ
UNIQUE(idea_id, sequence_number)
```

#### `file_attachments`
```sql
id              SERIAL PRIMARY KEY
chat_message_id FK → chat_messages CASCADE
conversation_id FK → conversations CASCADE
filename        TEXT NOT NULL
file_size       INTEGER NOT NULL
file_type       TEXT NOT NULL
s3_key          TEXT NOT NULL
extracted_text  TEXT
summary_text    TEXT
uploaded_by_user_id FK → users
created_at      TIMESTAMPTZ
```

#### `conversation_memories`
```sql
id              SERIAL PRIMARY KEY
conversation_id FK → conversations CASCADE
memory_source   TEXT NOT NULL
memories        JSONB NOT NULL
UNIQUE(conversation_id, memory_source)
```

### Summary Tables

#### `chat_summaries`
```sql
id              SERIAL PRIMARY KEY
conversation_id FK → conversations CASCADE
external_id     INTEGER NOT NULL
summary         TEXT NOT NULL
latest_message_id INTEGER NOT NULL
created_at      TIMESTAMPTZ
updated_at      TIMESTAMPTZ
```

#### `imported_conversation_summaries`
```sql
id              SERIAL PRIMARY KEY
conversation_id FK → conversations CASCADE
external_id     INTEGER NOT NULL
summary         TEXT NOT NULL
created_at      TIMESTAMPTZ
updated_at      TIMESTAMPTZ
```

### LLM Configuration Tables

#### `llm_prompts`
```sql
id              SERIAL PRIMARY KEY
prompt_type     TEXT NOT NULL
system_prompt   TEXT NOT NULL
is_active       BOOLEAN DEFAULT TRUE
created_by_user_id FK → users
created_at      TIMESTAMPTZ
UNIQUE(prompt_type) WHERE is_active = TRUE
```

#### `default_llm_parameters`
```sql
id              SERIAL PRIMARY KEY
prompt_type     TEXT UNIQUE NOT NULL
llm_provider    TEXT NOT NULL
llm_model       TEXT NOT NULL
created_by_user_id FK → users
created_at      TIMESTAMPTZ
updated_at      TIMESTAMPTZ
```

### Views

#### `conversation_dashboard_view`
Joins conversations with users, ideas, and latest chat messages for efficient dashboard queries.

### PostgreSQL Extensions
- `pg_trgm` - Trigram fuzzy search for conversation titles

---

## 6. Authentication

### Session Cookie Authentication

```
Cookie: session_token=<token>
```
- Set by Google OAuth callback
- HTTP-only, secure cookie
- Configurable expiration (`SESSION_EXPIRE_HOURS`)

### OAuth Flow

```
1. GET /api/auth/login
   → Redirect to Google OAuth with state token

2. Google OAuth consent
   → Redirect to /api/auth/callback?code=...&state=...

3. GET /api/auth/callback
   → Exchange code for tokens
   → Create/update user
   → Create session
   → Set cookie
   → Redirect to frontend
```

### Public Endpoints (No Auth)

- `/`, `/health`, `/docs`, `/openapi.json`, `/redoc`
- `/api/auth/login`, `/api/auth/callback`, `/api/auth/status`

### Using Authentication in Routes

```python
from app.middleware.auth import get_current_user

@router.get("/my-endpoint")
async def my_endpoint(request: Request):
    user = get_current_user(request)
    return {"user_id": user.id}
```

---

## 7. Streaming & Real-time

### Server-Sent Events (SSE)

Import and idea generation use SSE for real-time responses:

```
POST /api/conversations/import

Response: text/event-stream

Events:
- state: {"type": "state", "data": "importing"}
- state: {"type": "state", "data": "extracting_chat_keywords"}
- state: {"type": "state", "data": "retrieving_memories"}
- state: {"type": "state", "data": "generating"}
- content: {"type": "content", "data": "Title:\n..."}
- done: {"type": "done", "data": {...}}
- error: {"type": "error", "data": "..."}
- conflict: {"type": "conflict", "data": {...}}
```

### Idea Generation Flow

1. Import conversation from URL or create manual seed
2. Extract keywords from conversation
3. Retrieve memories from Mem0 service
4. Generate structured idea using LLM
5. Stream formatted sections to client
6. Persist idea to database
7. Return complete response

---

## 8. Configuration

### Environment Variables

**Required:**
```bash
# Database
DATABASE_URL=postgresql://user:pass@host:5432/db
# OR individual:
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=ae_scientist
POSTGRES_USER=postgres
POSTGRES_PASSWORD=password

# LLM APIs
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
XAI_API_KEY=xai-...

# Google OAuth
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
GOOGLE_REDIRECT_URI=http://localhost:8000/api/auth/callback

# AWS S3
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=us-east-1
AWS_S3_BUCKET_NAME=...
```

**Optional:**
```bash
# Server
PORT=8000
LOG_LEVEL=INFO
CORS_ORIGINS=http://localhost:3000

# Sessions
SESSION_EXPIRE_HOURS=24

# External Services
MEM0_API_URL=...
MEM0_USER_ID=...
METACOGNITION_API_URL=...
METACOGNITION_AUTH_TOKEN=...

# LLM Settings
IDEA_MAX_COMPLETION_TOKENS=4096

# Frontend
FRONTEND_URL=http://localhost:3000
```

---

## 9. Development

### Running the Server

```bash
cd server

# Install dependencies
uv sync

# Run development server
make dev

# Or manually:
uv run uvicorn app.main:app --reload --port 8000
```

### Database Migrations

```bash
cd server

# Apply all migrations
python migrate.py upgrade

# Check current version
python migrate.py current

# View history
python migrate.py history

# Create new migration
python migrate.py revision "description of change"
```

### Makefile Tasks

```bash
make install          # Install dependencies with uv
make lint            # Format & lint code (black, isort, ruff, mypy)
make test            # Run pytest tests
make dev             # Start dev server with migrations & hot reload
make migrate         # Run Alembic migrations
make export-openapi  # Generate OpenAPI schema
make gen-api-types   # Generate TypeScript types for frontend
```

### API Documentation

FastAPI auto-generates OpenAPI docs:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- OpenAPI JSON: `http://localhost:8000/openapi.json`

### Testing

```bash
cd server
make test

# Or:
uv run python -m pytest tests/
```
