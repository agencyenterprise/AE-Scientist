# AE-Scientist Documentation

This folder contains documentation to help engineers understand the AE-Scientist codebase.

## Project Summary

**AE-Scientist** is an autonomous AI research experiment system that uses Large Language Models (LLMs) and Vision Language Models (VLMs) to conduct complete research workflows—from ideation through paper generation.

Key capabilities:
- **4-Stage BFTS Pipeline**: Baseline → Tuning → Plotting → Ablation
- **LLM-Powered Code Generation**: Automated experiment implementation
- **VLM Plot Validation**: Quality assurance for generated visualizations
- **Paper Generation**: Automated research paper writeup with citations

---

## Documentation Index

### System Documentation
| Document | Description |
|----------|-------------|
| [Project Architecture](System/project_architecture.md) | Overall system architecture, project structure, tech stack |
| [Frontend Architecture](System/frontend_architecture.md) | Next.js frontend: feature-based architecture, conventions, migration guide |
| [Server Architecture](System/server_architecture.md) | FastAPI server: API routes, services, database schema, LLM integrations |
| [Orchestrator Architecture](System/orchestrator_architecture.md) | Next.js orchestrator: event processing, RunPod, MongoDB, state machine |

### Root-Level Documentation
| Document | Description |
|----------|-------------|
| [ARCHITECTURE.md](../ARCHITECTURE.md) | Detailed runtime execution flow for BFTS |
| [readme.md](../readme.md) | Setup instructions and usage guide |

### Standard Operating Procedures (SOPs)

#### Server SOPs
| Document | Description |
|----------|-------------|
| [Database Migrations](SOP/server_database_migrations.md) | Creating and running Alembic migrations |
| [API Routes](SOP/server_api_routes.md) | Adding FastAPI routes with authentication |
| [Services](SOP/server_services.md) | Creating services and database mixins |

#### Frontend SOPs
| Document | Description |
|----------|-------------|
| [Pages](SOP/frontend_pages.md) | Adding Next.js App Router pages |
| [Features](SOP/frontend_features.md) | Feature-based component organization |
| [API Hooks](SOP/frontend_api_hooks.md) | Creating custom hooks for API calls |

#### Orchestrator SOPs
| Document | Description |
|----------|-------------|
| [API Routes](SOP/orchestrator_api_routes.md) | Adding Next.js API route handlers |
| [Event Types](SOP/orchestrator_event_types.md) | Defining CloudEvents schemas and handlers |
| [MongoDB Collections](SOP/orchestrator_mongodb.md) | Creating repositories and schemas |

---

## Folder Structure

```
.agent/
├── README.md           # This file - documentation index
├── System/             # System & architecture documentation
│   ├── project_architecture.md      # Overall project
│   ├── frontend_architecture.md     # Frontend details
│   ├── server_architecture.md       # Server details
│   └── orchestrator_architecture.md # Orchestrator details
├── SOP/                # Standard operating procedures
│   ├── server_database_migrations.md
│   ├── server_api_routes.md
│   ├── server_services.md
│   ├── frontend_pages.md
│   ├── frontend_features.md
│   ├── frontend_api_hooks.md
│   ├── orchestrator_api_routes.md
│   ├── orchestrator_event_types.md
│   └── orchestrator_mongodb.md
└── Tasks/              # PRD & implementation plans (future)
```

---

## Quick Start

For setup and running experiments, see [readme.md](../readme.md).

**Local Setup**:
```bash
git clone https://github.com/agencyenterprise/AE-Scientist.git
cd AE-Scientist
uv sync --extra gpu
source .venv/bin/activate
```

**Run Stage 1 Only**:
```bash
python launch_stage1_only.py bfts_config.yaml
```

**Run Full Pipeline**:
```bash
python launch_scientist_bfts.py bfts_config.yaml
```

---

## Key Entry Points

| Script | Purpose |
|--------|---------|
| `launch_scientist_bfts.py` | Full end-to-end pipeline |
| `launch_stage1_only.py` | Stage 1 only |
| `launch_stage2_from_run.py` | Resume from Stage 2 |
| `launch_stage3_from_run.py` | Resume from Stage 3 |
| `launch_stage4_from_run.py` | Resume from Stage 4 |

---

## Environment Variables

**Required**:
```bash
OPENAI_API_KEY=sk-...           # LLM queries
HUGGINGFACE_HUB_TOKEN=hf_...    # Model/dataset downloads
```

See [readme.md](../readme.md) for full environment variable reference.
