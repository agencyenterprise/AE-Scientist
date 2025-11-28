# AE-Scientist System Architecture

## Related Documentation
- [README.md](../README.md) - Documentation index
- [ARCHITECTURE.md](../../ARCHITECTURE.md) - Detailed runtime execution flow
- [readme.md](../../readme.md) - Setup and usage instructions

---

## 1. Project Overview

**AE-Scientist** is an autonomous AI research experiment system that uses Large Language Models (LLMs) and Vision Language Models (VLMs) to conduct complete research workflows—from ideation through paper generation.

### Core Capabilities
- **Automated Research Pipeline**: Orchestrates a multi-stage Breadth-First Tree Search (BFTS) for exploring experimental implementations
- **Code Generation**: LLM-powered code generation for experiments, hyperparameter tuning, and visualization
- **Plot Validation**: VLM-based analysis of generated plots for quality assurance
- **Paper Generation**: Automated research paper writeup with citation gathering and review

### BFTS 4-Stage Pipeline
1. **Stage 1 - Baseline**: Generate initial experiment implementations from a research idea
2. **Stage 2 - Tuning**: Hyperparameter optimization of the best baseline implementation
3. **Stage 3 - Plotting**: Generate visualizations and plots for results
4. **Stage 4 - Ablation**: Run ablation studies to validate design choices

---

## 2. Project Structure

```
AE-Scientist/
├── ai_scientist/              # Core AI Scientist engine
│   ├── treesearch/           # BFTS orchestration and stages
│   ├── llm/                  # LLM/VLM integration layer
│   ├── ideation/             # Research idea generation
│   ├── perform_writeup.py    # Paper generation
│   └── perform_llm_review.py # Paper review
│
├── server/                    # FastAPI web server
│   ├── app/                  # API routes, models, services
│   └── database_migrations/  # Alembic migrations
│
├── frontend/                  # Next.js React UI
│   └── src/                  # Components, hooks, contexts
│
├── orchestrator/              # RunPod container management
├── worker/                    # Worker process utilities
│
├── launch_scientist_bfts.py   # Full pipeline entry point
├── launch_stage1_only.py      # Stage 1 only entry point
├── launch_stage2_from_run.py  # Resume from Stage 2
├── launch_stage3_from_run.py  # Resume from Stage 3
├── launch_stage4_from_run.py  # Resume from Stage 4
│
├── bfts_config.yaml           # Default configuration
├── bfts_config_gpt-5.yaml     # GPT-5 model variant
├── bfts_config_claude-haiku.yaml  # Claude Haiku variant
│
├── docker-compose.yml         # PostgreSQL container
├── pyproject.toml             # Python dependencies
└── Makefile                   # Development commands
```

### Key Entry Points
| Script | Purpose |
|--------|---------|
| `launch_scientist_bfts.py` | Full end-to-end pipeline (all 4 stages + writeup + review) |
| `launch_stage1_only.py` | Run Stage 1 only (initial implementation) |
| `launch_stage2_from_run.py` | Resume from Stage 2 |
| `launch_stage3_from_run.py` | Resume from Stage 3 |
| `launch_stage4_from_run.py` | Resume from Stage 4 |

---

## 3. AI Scientist Engine (`/ai_scientist`)

### Treesearch Architecture

The system uses a three-tier agent hierarchy:

```
┌─────────────────────────────────────────────────────────────┐
│                    AgentManager                              │
│  (Orchestrator - long-lived per run)                        │
│  • Owns staged lifecycle via StageMeta                      │
│  • Creates/owns Journal per stage                           │
│  • Maintains stage_history and checkpoints                  │
│  • Decides when stages complete                             │
└─────────────────────┬───────────────────────────────────────┘
                      │ creates
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                    ParallelAgent                             │
│  (Parallel executor - short-lived per substage)             │
│  • Manages ProcessPoolExecutor (spawn)                      │
│  • Handles GPU assignment via GPUManager                    │
│  • Selects nodes (draft/debug/improve)                      │
│  • Collects results, emits events                           │
└─────────────────────┬───────────────────────────────────────┘
                      │ submits work to
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                    MinimalAgent                              │
│  (Per-worker codegen - ephemeral per task)                  │
│  • Builds prompts and calls LLM                             │
│  • Drafts/improves/debugs code                              │
│  • Parses execution outputs                                 │
│  • Delegates stage-specific ops to Stage classes            │
└─────────────────────────────────────────────────────────────┘
```

### Stage System (`/ai_scientist/treesearch/stages/`)

| Stage Class | Purpose |
|-------------|---------|
| `Stage1Baseline` | Initial implementation from research idea |
| `Stage2Tuning` | Hyperparameter optimization |
| `Stage3Plotting` | Visualization generation with VLM validation |
| `Stage4Ablation` | Ablation studies to validate design choices |

Each stage provides:
- Stage defaults (`MAIN_STAGE_SLUG`, `DEFAULT_GOALS`)
- Static methods for stage-specific operations
- Completion evaluation logic

### Key Modules

| Module | Location | Purpose |
|--------|----------|---------|
| `agent_manager.py` | `treesearch/` | Orchestrates staged lifecycle |
| `parallel_agent.py` | `treesearch/` | Parallel execution with ProcessPoolExecutor |
| `worker_process.py` | `treesearch/` | Worker entrypoint, code execution sandbox |
| `journal.py` | `treesearch/` | Experiment state tracking/serialization |
| `interpreter.py` | `treesearch/` | Code execution sandbox |
| `codegen_agent.py` | `treesearch/` | LLM-based code generation |

### LLM/VLM Integration (`/ai_scientist/llm/`)

All LLM/VLM calls are centralized in this package:

```
llm/
├── llm.py              # Core LLM query interface
├── vlm.py              # Vision Language Model interface
├── token_tracker.py    # Token usage tracking
├── providers.py        # LLM provider abstraction
└── query/              # Backend query implementations
```

Supported providers: OpenAI, Anthropic Claude

### Execution Flow

1. **Launch script** loads research idea, prepares workspace, calls experiment runner
2. **Experiment runner** creates `AgentManager`, renders UI, calls `manager.run()`
3. **AgentManager** initializes `StageMeta` (baseline) and sets up initial journal
4. **For each substage**:
   - Curates task description based on stage type
   - Creates `ParallelAgent` with carryover best nodes
   - Calls `agent.step(exec_callback)` until substage completes
5. **When main stage completes**:
   - Runs multi-seed evaluation
   - Performs plot aggregation
   - Transitions to next main stage
6. **Journals and checkpoints** saved to `logs/` throughout

### Output Artifacts

```
workspaces/
├── logs/<run_id>/              # Experiment logs and journal
│   ├── stage_*/               # Per-stage results
│   │   └── best_solution_*.py # Best implementation code
│   └── experiment_results/    # Generated plots
├── figures/                    # Aggregated plots
└── <run_id>.pdf               # Generated research paper
```

---

## 4. Web Application

### Frontend (`/frontend`)

**Tech Stack**: Next.js 15 + React 19 + TypeScript + Tailwind CSS

| Directory | Purpose |
|-----------|---------|
| `src/app/` | Next.js App Router (file-based routing) |
| `src/components/` | React components (ProjectDraft, ConversationView, etc.) |
| `src/contexts/` | React contexts (AuthContext, DashboardContext) |
| `src/hooks/` | Custom hooks (useAuth, useSearch) |
| `src/lib/` | Utilities, API adapters, config |
| `src/types/` | TypeScript types (auto-generated from OpenAPI) |

**Key Features**:
- Conversation import from ChatGPT, Claude, Grok URLs
- Project draft generation with AI
- Real-time streaming chat
- Vector-based semantic search

### Server (`/server`)

**Tech Stack**: FastAPI + PostgreSQL + Alembic + LangChain

| Directory | Purpose |
|-----------|---------|
| `app/api/` | REST API routes |
| `app/models/` | Pydantic models |
| `app/services/` | Business logic services |
| `app/middleware/` | Auth middleware |
| `database_migrations/` | Alembic schema migrations |

**API Routes**:
| Prefix | Purpose |
|--------|---------|
| `/api/auth` | Google OAuth, session management |
| `/api/conversations` | Conversation import, CRUD, ideas |
| `/api/llm-defaults` | LLM model configuration |
| `/api/llm-prompts` | System prompt management |

**LLM Services**:
- OpenAI (GPT-4, GPT-4o, GPT-4.1)
- Anthropic (Claude Opus, Sonnet, Haiku)
- xAI Grok

**Database Tables**:
- `users`, `user_sessions` - Authentication
- `conversations` - Imported chats
- `ideas`, `idea_versions` - AI-generated research ideas
- `chat_messages`, `chat_summaries` - Live chat
- `file_attachments` - S3 file references

---

## 5. Infrastructure

### Orchestrator (`/orchestrator`)

TypeScript/Node.js control plane for:
- RunPod container provisioning (`create_runpod.ts`)
- Multi-machine deployment support
- Experiment execution orchestration

### Worker (`/worker`)

Worker process utilities for:
- Event emission and experiment monitoring
- Job management for distributed execution

### Environment Variables

**Required for AI Scientist**:
```bash
OPENAI_API_KEY=sk-...           # LLM queries
HUGGINGFACE_HUB_TOKEN=hf_...    # Model/dataset downloads
HF_TOKEN=hf_...                 # Same as above
```

**Optional**:
```bash
OPENAI_BASE_URL=...             # Custom LLM endpoint
ANTHROPIC_API_KEY=...           # When using Claude models
```

**For Web Application**:
```bash
DATABASE_URL=...                # PostgreSQL connection
GOOGLE_CLIENT_ID=...            # OAuth
GOOGLE_CLIENT_SECRET=...
AWS_ACCESS_KEY_ID=...           # S3 file storage
AWS_SECRET_ACCESS_KEY=...
AWS_S3_BUCKET_NAME=...
```

### Docker Setup

```bash
# Start PostgreSQL for full deployment
docker-compose up -d

# Build and run server
cd server && docker build -t ae-scientist-server .

# Build and run frontend
cd frontend && docker build -t ae-scientist-frontend .
```

---

## 6. Technology Stack Summary

### Python Stack (AI Scientist)
| Category | Technologies |
|----------|--------------|
| LLM Integration | OpenAI, Anthropic Claude, LangChain |
| ML/Data | PyTorch, scikit-learn, transformers, LightGBM, XGBoost |
| Visualization | Matplotlib, Seaborn |
| Code Quality | Black, ruff, mypy, isort |

### Web Stack
| Layer | Technologies |
|-------|--------------|
| Frontend | Next.js 15, React 19, TypeScript, Tailwind CSS |
| Server | FastAPI, PostgreSQL, Alembic, LangChain |
| Auth | Google OAuth 2.0, session cookies |
| Storage | AWS S3 |

### Infrastructure
| Component | Technologies |
|-----------|--------------|
| Containerization | Docker, docker-compose |
| GPU Cloud | RunPod |
| Package Manager | uv (Python), pnpm (Node.js) |
