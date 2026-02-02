# AE Scientist - Server

A collaborative platform that transforms LLM conversations into structured research ideas through AI-guided refinement.

## How It Works

**AE Scientist** streamlines the journey from conversational ideas to structured project execution:

1. **Import Conversations**: Paste LLM share URLs to import rich conversational content that contains research ideas, technical discussions, or experimental concepts.

2. **Generate Research Ideas**: AI analyzes the imported conversations and automatically generates structured research proposals with hypotheses, experiments, and expected outcomes.

3. **Refine Through Dialogue**: Engage in an interactive refinement process where you can prompt the AI to adjust, expand, or focus the research scope. Ask for more experimental detail, refine hypotheses, or explore different methodologies.



### Setup

1. **Set up Clerk Authentication (REQUIRED)**
   
   Create a Clerk application for user authentication:
   
   a. Go to [Clerk Dashboard](https://dashboard.clerk.com/)
   b. Create a new application (or select an existing one)
   c. In your application settings:
      - Navigate to **API Keys** section
      - Copy your **Publishable Key** (starts with `pk_test_` or `pk_live_`)
      - Copy your **Secret Key** (starts with `sk_test_` or `sk_live_`)
   d. Configure allowed domains and redirect URLs as needed
   e. (Optional) Configure social login providers, email/password settings, etc.

2. **Environment Configuration**
   ```bash
   # Copy environment templates
   cp server/env.example server/.env
   cp frontend/env.local.example frontend/.env.local
   
   # IMPORTANT: Edit both .env files with your Clerk credentials
   # In server/.env:
   CLERK_SECRET_KEY="sk_test_your_clerk_secret_key"
   CLERK_PUBLISHABLE_KEY="pk_test_your_clerk_publishable_key"
   
   # In frontend/.env.local:
   CLERK_SECRET_KEY="sk_test_your_clerk_secret_key"
   NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY="pk_test_your_clerk_publishable_key"
   ```

3. **Setup using Makefile (Recommended)**
   ```bash
   # Install all dependencies (creates virtual environment automatically)
   make install
   
   # Start development servers
   make dev-server    # Starts FastAPI server using virtual environment
   make dev-frontend   # Starts Next.js server
   ```

   **🔒 First Run**: Visit `http://localhost:3000` → You'll be redirected to login page → Sign in with preferred method!

4. **Manual Setup (Alternative)**
   
   **Backend:**
   ```bash
   make venv-backend                    # Create virtual environment
   make install-backend                 # Install dependencies in venv
   make dev-backend                     # Start server using venv
   ```
   
   **Frontend:**
   ```bash
   make install-frontend               # Install dependencies
   make dev-frontend                   # Start development server
   ```

### Development Servers
- **Frontend**: http://localhost:3000
- **Backend**: http://localhost:8000

### Credits & Billing

Refinement and research runs can now be gated behind prepaid credits. Configure the following
environment variables in `server/.env` to enable Stripe-powered top-ups:

| Variable | Description |
| --- | --- |
| `MIN_USER_CREDITS_FOR_CONVERSATION` | Minimum credits required before a user can refine/import a conversation |
| `MIN_USER_CREDITS_FOR_RESEARCH_PIPELINE` | Minimum credits required before launching a RunPod research run |
| `STRIPE_SECRET_KEY` | Server-side Stripe key used for Checkout + webhook verification |
| `STRIPE_WEBHOOK_SECRET` | Secret used to validate `checkout.session.*` events |
| `STRIPE_CHECKOUT_SUCCESS_URL` | Optional default success redirect (defaults to `/billing?success=1`) |
| `STRIPE_PRICE_TO_CREDITS` | JSON map of `price_id -> credits`, e.g. `{"price_small":100,"price_large":800}` |
| `JSON_MODEL_PRICE_PER_MILLION_IN_CENTS` | JSON map of model pricing per million tokens (input/output in cents), e.g. `{"anthropic":{"claude-3-opus-20240229":{"input":1500,"output":7500}},...}` |
| `WHITELIST_EMAILS_FREE_CREDIT` | Comma-separated list of email addresses that receive free credits upon registration |
| `RESEARCH_RUN_CREDITS_PER_MINUTE` | Credits charged per minute for research pipeline runs |
| `CHAT_MESSAGE_CREDIT_COST` | Credits charged per chat message |

The backend exposes:

- `GET /api/billing/wallet` – current balance + recent ledger entries
- `GET /api/billing/packs` – configured Stripe prices and credit amounts
- `POST /api/billing/checkout-session` – creates a Checkout session for the selected pack
- `POST /api/billing/stripe-webhook` – receives Stripe events (whitelisted in auth middleware)

On the frontend, add the corresponding public variables (`NEXT_PUBLIC_*`) so the Billing page can
display thresholds and redirect URLs.

### MCP Server Integration (Claude Code)

AE Scientist exposes an MCP (Model Context Protocol) server that allows you to run research pipelines directly from Claude Code.

#### How It Works

1. **Generate an API Key**: In the frontend, click your profile dropdown and select "Integrate with Claude" to generate an MCP API key.

2. **Add the MCP Server to Claude Code**: Run the command shown in the modal:
   ```bash
   claude mcp add-json research-pipeline '{"type":"http","url":"https://your-backend-url/mcp","headers":{"Authorization":"Bearer mcp_your_api_key"}}'
   ```

3. **Use the `run_pipeline` Tool**: In Claude Code, you can now use the `run_pipeline` tool to start research runs:
   ```
   Use the run_pipeline tool to research "Investigating novel attention mechanisms"
   ```

#### Available Tools

| Tool | Description |
| --- | --- |
| `run_pipeline` | Start a research pipeline run with a research idea and detailed content |

The `run_pipeline` tool accepts:
- `idea`: A concise, descriptive title for the research idea
- `content`: Markdown content with sections for hypothesis, related work, abstract, experiments, expected outcomes, and risk factors

#### API Endpoints

| Endpoint | Description |
| --- | --- |
| `POST /mcp` | MCP JSON-RPC endpoint (authenticates via Bearer token with MCP API key) |
| `GET /api/mcp-integration/key` | Get current user's MCP API key (masked) |
| `POST /api/mcp-integration/generate-key` | Generate a new MCP API key |
| `DELETE /api/mcp-integration/key` | Revoke the current MCP API key |

#### Response

When a pipeline is launched successfully, the tool returns:
- `run_id`: The research run ID
- `conversation_id`: The conversation ID
- `url`: Direct link to view the run in the frontend
- Pod information (pod_id, pod_name, gpu_type)

### Playwright Setup

Playwright is used for browser automation in the server (e.g., scraping and browser-driven tests). After installing backend dependencies, install the browser binaries locally.

```bash
# Install Playwright browsers inside the server virtualenv
cd server
. .venv/bin/activate  # or use your preferred venv activation
uv run playwright install firefox

# Verify installation
uv run playwright --version
```

Docker users: the server image installs Firefox via Playwright during build, so no additional setup is required inside the container.

### Database Setup

This application uses **PostgreSQL** as its database. You'll need to set up a PostgreSQL database before running the backend.

#### Option 1: Use Railway PostgreSQL (Recommended for Production)
1. Create a PostgreSQL database on Railway
2. Copy the `DATABASE_URL` from Railway
3. Set it in your `.env` file

#### Option 2: Local PostgreSQL Setup
1. Install PostgreSQL on your machine

2. Create the database and user:
   ```bash
   # Connect to PostgreSQL as superuser
   psql -U postgres
   
   # Create user first
   CREATE USER ae_scientist_user WITH PASSWORD 'your_password';
   
   # Create database owned by the application user
   CREATE DATABASE ae_scientist OWNER ae_scientist_user;
   
   # Exit psql
   \q
   ```

3. Update the PostgreSQL environment variables in `.env`:
   ```bash
   POSTGRES_HOST="localhost"
   POSTGRES_PORT="5432"
   POSTGRES_DB="ae_scientist"
   POSTGRES_USER="ae_scientist_user"
   POSTGRES_PASSWORD="your_secure_password"  # Use the password you set above
   ```

4. Run migrations:
   ```bash
   # Apply database migrations (tables will be created with correct ownership)
   make migrate-db
   ```

### Database Migrations

This application uses **Alembic** for database schema management. The database schema is now versioned and managed through migration files.

#### Migration Commands

```bash
# Apply all pending migrations (required for first setup)
make migrate-db

# Create a new migration (for developers making schema changes)
cd backend && python migrate.py revision "add user preferences table"
```

#### First Setup
When setting up the application for the first time:

1. Set up your PostgreSQL database (see above)
2. Run `make migrate-db` to create all tables
3. Start the application with `make dev-backend`

#### Development Workflow
- The `make dev-backend` command automatically runs migrations before starting the server
- All database schema changes must be done through migration files
- Never modify database schema directly in production

#### Creating New Migrations
When you need to modify the database schema:

1. **Create the migration file:**
   ```bash
   cd backend
   python migrate.py revision "descriptive message about the change"
   ```

2. **Edit the generated migration file** in `backend/database_migrations/versions/`
   - Add your SQL DDL statements in the `upgrade()` function
   - Use `op.execute("CREATE TABLE ...")` for raw SQL
   - Add corresponding DROP statements in `downgrade()` if needed

3. **Test the migration:**
   ```bash
   make migrate-db  # Apply the new migration
   ```

#### Migration Files
- Location: `backend/database_migrations/versions/`
- Naming: Sequential numbers (0001_, 0002_, etc.)
- Each migration includes upgrade and downgrade functions

### AWS S3 Setup (Required for File Uploads)

This application supports file uploads (images and PDFs) stored in AWS S3. You'll need to set up an S3 bucket and configure IAM permissions.

#### 1. Create S3 Bucket
1. Log into the AWS Console
2. Navigate to S3 service
3. Create a new bucket with a unique name (e.g., `agi-judds-files-bucket`)
4. Block public access (recommended for security)

#### 2. Create IAM User and Permissions
1. Navigate to IAM service in AWS Console
2. Create a new user (e.g., `agi-judds-s3-user`)
3. Create a custom policy with the following permissions:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:GetObject",
                "s3:PutObject",
                "s3:DeleteObject",
                "s3:ListBucket"
            ],
            "Resource": [
                "arn:aws:s3:::your-bucket-name",
                "arn:aws:s3:::your-bucket-name/*"
            ]
        }
    ]
}
```

4. Attach the policy to your user
5. Generate access keys for the user

#### 3. Configure Environment Variables
Add the following to your `backend/.env` file:

```bash
# AWS S3 Configuration for File Uploads
AWS_ACCESS_KEY_ID="your_aws_access_key_id_here"
AWS_SECRET_ACCESS_KEY="your_aws_secret_access_key_here"
AWS_REGION="us-east-1"  # or your preferred region
AWS_S3_BUCKET_NAME="your_s3_bucket_name_here"
```

## Running Tests
```bash
# Create/recreate test database manually
make create-test-db

```

## Environment Variables

### Backend Configuration

Copy `backend/env.example` to `backend/.env` and customize as needed:

```bash
# Database Configuration (PostgreSQL - REQUIRED)
DATABASE_URL="postgresql://ae_scientist_user:your_password@localhost:5432/ae_scientist"
POSTGRES_USER="ae_scientist_user"
POSTGRES_PASSWORD="your_password"

# Authentication Configuration
SESSION_EXPIRE_HOURS="24"
FRONTEND_URL="http://localhost:3000"

# API Keys (Optional - for full functionality)
OPENAI_API_KEY="your-openai-api-key-here"          # For LLM services
ANTHROPIC_API_KEY="your-anthropic-api-key-here"    # For Claude models
XAI_API_KEY="your-xai-api-key-here"                # For Grok models
AWS_ACCESS_KEY_ID="your-aws-access-key"             # For file uploads
AWS_SECRET_ACCESS_KEY="your-aws-secret"             # For file uploads
AWS_S3_BUCKET_NAME="your-s3-bucket"                 # For file uploads

# Research pipeline configuration
TELEMETRY_WEBHOOK_URL="https://your-backend-host/api/research-pipeline/events"
HF_TOKEN="your_huggingface_token"

# Research pipeline monitor settings (all required)
PIPELINE_MONITOR_POLL_INTERVAL_SECONDS="60"
PIPELINE_MONITOR_HEARTBEAT_TIMEOUT_SECONDS="60"
PIPELINE_MONITOR_MAX_MISSED_HEARTBEATS="5"
PIPELINE_MONITOR_STARTUP_GRACE_SECONDS="600"
RUNPOD_SUPPORTED_GPUS="NVIDIA GeForce RTX 5090,NVIDIA RTX PRO 6000 Blackwell Server Edition,NVIDIA GeForce RTX 3090,NVIDIA RTX A4000,NVIDIA RTX A4500,NVIDIA RTX A5000"
RUN_POD_SSH_ACCESS_KEY="-----BEGIN OPENSSH PRIVATE KEY-----\n...replace...\n-----END OPENSSH PRIVATE KEY-----"
FAKE_RUNPOD_BASE_URL="http://127.0.0.1:9000"          # Point RunPodManager at the fake server
FAKE_RUNPOD_PORT="9000"                               # Port for the fake RunPod server
FAKE_RUNPOD_GRAPHQL_URL="http://127.0.0.1:9000/graphql"

```

### Frontend Configuration

Copy `frontend/env.local.example` to `frontend/.env.local`:

```bash
# API Configuration
NEXT_PUBLIC_API_BASE_URL="http://localhost:8000"

# Development Settings  
NEXT_PUBLIC_ENVIRONMENT="development"
```

## Authentication

This application now requires **Clerk authentication** for all users.

### User Authentication Flow
1. Users visit the application and are redirected to `/login`
2. Clerk sign in page is displayed
3. Clerk validates the user and redirects back to the application
4. Users can access all features and their session persists for 24 hours in local storage
5. Users can sign out at any time from the dashboard header

### Security Features
- HTTP-only secure session cookies
- Automatic session expiration and cleanup
- Protected API endpoints (all routes except `/health`, `/docs`, `/auth/*`)

**Important:**
- `.env` and `.env.local` files are ignored by git for security
- `env.example` files provide templates with default values
- **Clerk credentials are required** - the app won't start without them
- Frontend environment variables must be prefixed with `NEXT_PUBLIC_` to be accessible in the browser

## Available Scripts

### Frontend
```bash
npm run dev          # Start development server
npm run build        # Build for production
npm run lint         # Run ESLint
npm run lint:fix     # Fix ESLint issues
npm run format       # Format code with Prettier
npm run format:check # Check code formatting
npm run style        # Lint CSS with Stylelint
npm run gen:api-types            # Generate TS types from running backend /openapi.json
npm run gen:api-types:from-file  # Generate TS types from backend/openapi.json
```

### Backend
```bash
python -m uvicorn app.main:app --reload  # Start development server
python -m black .                        # Format Python code
python -m isort .                         # Sort Python imports
python -m flake8 .                        # Lint Python code
python -m mypy .                          # Type check Python code
```

## Fake RunPod server (fast local validation)

Use this to exercise the research pipeline flow without provisioning a real RunPod GPU.

- Start the fake RunPod server in a separate terminal:
  - Set `FAKE_RUNPOD_PORT`, `FAKE_RUNPOD_BASE_URL`, and `FAKE_RUNPOD_GRAPHQL_URL`.
  - Run `make fake-runpod`.
  - **Speed up testing** with `make fake-runpod SPEED=N` where N is the speed multiplier (e.g., `SPEED=10` runs 10× faster with wait times reduced to 10%).
- Point the launcher at the fake endpoint via `FAKE_RUNPOD_BASE_URL` (and `FAKE_RUNPOD_GRAPHQL_URL`).
- Behavior:
  - Exposes `/pods`, `/pods/{id}`, `/billing/pods`, and `/graphql` with the same shape the real RunPod API uses.
  - Creates a per-run fake runner that finishes in ~10 minutes (or faster with `SPEED`), emitting:
    - `run-started`, heartbeats, stage progress (4 stages × 3 iterations), substage-completed, logs, and `run-finished`.
    - Token usage, hardware stats, figure reviews, and LLM review webhooks.
    - One small fake artifact uploaded to S3 and recorded in `rp_artifacts`.
  - Pod metadata uses `pod_id=fake-...`, `publicIp=127.0.0.1`, `portMappings={"22": "0"}` so readiness checks pass; SSH log upload is effectively skipped.

## API Type Generation

The frontend uses types generated directly from the backend's OpenAPI schema. Do not define duplicate hand-written API types.

- Generate schema and types from file:
  ```bash
  make gen-api-types
  ```
  This exports `backend/openapi.json` and writes `frontend/src/types/api.gen.ts`.

- Or generate directly from a running backend:
  ```bash
  cd frontend && npm run gen:api-types
  ```

During builds, `prebuild` generates types from `backend/openapi.json` to avoid drift.