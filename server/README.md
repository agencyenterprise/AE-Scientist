# AE Scientist - Server

A collaborative platform that transforms LLM conversations into structured research ideas through AI-guided refinement.

## How It Works

**AE Scientist** streamlines the journey from conversational ideas to structured project execution:

1. **Import Conversations**: Paste LLM share URLs to import rich conversational content that contains research ideas, technical discussions, or experimental concepts.

2. **Generate Research Ideas**: AI analyzes the imported conversations and automatically generates structured research proposals with hypotheses, experiments, and expected outcomes.

3. **Refine Through Dialogue**: Engage in an interactive refinement process where you can prompt the AI to adjust, expand, or focus the research scope. Ask for more experimental detail, refine hypotheses, or explore different methodologies.



### Prerequisites (macOS only)

If you're developing on **macOS**, install the required system dependency:

```bash
# Install libmagic (required for file type detection)
brew install libmagic
```

This is automatically included in Docker/Linux environments but must be manually installed on macOS.

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
   # Copy environment template
   cp server/env.example server/.env

   # Edit server/.env with your Clerk credentials
   CLERK_SECRET_KEY="sk_test_your_clerk_secret_key"
   CLERK_PUBLISHABLE_KEY="pk_test_your_clerk_publishable_key"
   ```

   For frontend configuration, see [Frontend Documentation](../frontend/README.md).

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

   **Server:**
   ```bash
   make install-server                  # Install dependencies
   make dev-server                      # Start server
   ```

   For frontend setup, see [Frontend Documentation](../frontend/README.md).

### Development Server
- **Server**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs

### Billing

Operations are billed based on actual costs in cents. Users must maintain a minimum balance before starting operations. Configure the following environment variables in `server/.env`:

#### Minimum Balance Requirements

| Variable | Description | Default |
| --- | --- | --- |
| `MIN_BALANCE_CENTS_FOR_RESEARCH_PIPELINE` | Minimum balance (cents) before launching a research run | 5000 ($50.00) |
| `MIN_BALANCE_CENTS_FOR_CHAT_MESSAGE` | Minimum balance (cents) before sending a chat message | 10 ($0.10) |
| `MIN_BALANCE_CENTS_FOR_PAPER_REVIEW` | Minimum balance (cents) before paper review | 100 ($1.00) |

#### Cost Calculation

| Variable | Description |
| --- | --- |
| `JSON_MODEL_PRICE_PER_MILLION_IN_CENTS` | JSON map of model pricing per million tokens (input/output/cached_input in cents) |

**How billing works:**
- **Chat messages**: Charged actual LLM token cost after message completes
- **Conversation import**: Charged actual LLM cost after import completes
- **Research runs**: Periodic "hold" transactions during execution, then reconciled with actual RunPod billing at termination
- **Paper review**: Charged actual LLM token cost after review completes

#### Stripe Configuration

| Variable | Description |
| --- | --- |
| `STRIPE_SECRET_KEY` | Server-side Stripe API key (starts with `sk_test_` or `sk_live_`) |
| `STRIPE_WEBHOOK_SECRET` | Webhook signing secret (starts with `whsec_`) |
| `STRIPE_CHECKOUT_SUCCESS_URL` | Success redirect URL after checkout (e.g., `https://yourapp.com/billing?success=1`) |
| `STRIPE_PRICE_IDS` | Comma-separated list of Stripe Price IDs to show as funding options |

**Note:** Stripe purchases use 1:1 mapping - pay $10.00 → get 1000 cents ($10.00) in wallet balance.

#### Stripe Webhook Setup

1. **Create a webhook endpoint** in the [Stripe Dashboard](https://dashboard.stripe.com/webhooks):
   - **Endpoint URL**: `https://your-domain.com/api/billing/stripe-webhook`
   - **API version**: Use your account's default API version

2. **Select the following events** to listen to:

   | Event | Purpose |
   | --- | --- |
   | `checkout.session.completed` | Credits wallet when payment succeeds |
   | `checkout.session.expired` | Marks abandoned checkout sessions |
   | `refund.created` | Deducts refunded amount from wallet |

3. **Copy the signing secret** (`whsec_...`) and set it as `STRIPE_WEBHOOK_SECRET`

**Local development with Stripe CLI:**
```bash
# Install Stripe CLI, then forward webhooks to your local server
stripe listen --forward-to http://localhost:8000/api/billing/stripe-webhook

# The CLI will print a webhook signing secret - use it for local testing
```

#### Creating Stripe Prices

Create one-time prices in the [Stripe Dashboard](https://dashboard.stripe.com/prices) or via CLI:
```bash
# Example: Create a $10 funding option
stripe prices create \
  --unit-amount 1000 \
  --currency usd \
  --product "prod_xxx" \
  --nickname "\$10 Wallet Funding"
```

Add the resulting Price IDs (e.g., `price_xxx,price_yyy`) to `STRIPE_PRICE_IDS`.

#### Admin Credit Management

Admins can manage user credits through the `/admin` page in the frontend. This replaces the previous environment variable-based email whitelist.

**Setup:**
1. Manually set admin users in the database:
   ```sql
   UPDATE users SET is_admin = true WHERE email = 'admin@example.com';
   ```

**Features:**
- **View user balances**: Search and browse all active users with their current wallet balances
- **Add credit to users**: Grant credits to any active user with a required description for audit trail
- **Pending credits**: Pre-grant credits to emails that haven't registered yet - credits are automatically claimed when the user signs up

### MCP Server Integration (Claude Code & Cursor)

AE Scientist exposes an MCP (Model Context Protocol) server that allows you to run research pipelines directly from Claude Code or Cursor.

#### How It Works

1. **Generate an API Key**: In the frontend, click your profile dropdown and select "MCP Integration" to generate an MCP API key.

2. **Add the MCP Server**:

   **For Claude Code**, run this command in your terminal:
   ```bash
   claude mcp add-json research-pipeline '{"type":"http","url":"https://your-server-url/mcp","headers":{"Authorization":"Bearer mcp_your_api_key"}}'
   ```

   **For Cursor**, add this to your `.cursor/mcp.json` file:
   ```json
   {
     "mcpServers": {
       "research-pipeline": {
         "url": "https://your-server-url/mcp",
         "headers": {
           "Authorization": "Bearer mcp_your_api_key"
         }
       }
     }
   }
   ```

3. **Use the `run_pipeline` Tool**: You can now use the `run_pipeline` tool to start research runs:
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


#### Response

When a pipeline is launched successfully, the tool returns:
- `run_id`: The research run ID
- `conversation_id`: The conversation ID
- `url`: Direct link to view the run in the frontend
- Pod information (pod_id, pod_name, gpu_type)

### Playwright Setup

Playwright is used for browser automation in the server (e.g., scraping and browser-driven tests). After installing server dependencies, install the browser binaries locally.

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

This application uses **PostgreSQL** as its database. You'll need to set up a PostgreSQL database before running the server.

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

### Redis Setup (Required for SSE Event Streaming)

Redis is used for real-time event streaming (Server-Sent Events) to broadcast research pipeline progress and narrator updates to connected clients. This enables multi-worker deployments where webhooks and SSE connections may be handled by different workers.

#### Option 1: Use Makefile (Recommended for Local Development)

```bash
# Start Redis container (uses redis:7-alpine image)
make redis

# Stop Redis container
make redis-stop

# Remove Redis container completely
make redis-rm
```

#### Option 2: Use Railway Redis (Recommended for Production)
1. Add a Redis plugin to your Railway project
2. Copy the `REDIS_URL` from Railway
3. Set it in your `.env` file

#### Option 3: Local Redis Installation
```bash
# macOS
brew install redis
brew services start redis

# Linux
sudo apt install redis-server
sudo systemctl start redis
```

#### Configuration

| Variable | Description | Default |
| --- | --- | --- |
| `REDIS_URL` | Redis connection URL | `redis://localhost:6379` |
| `REDIS_STREAM_MAXLEN` | Max events to keep per stream (approximate) | `1000` |
| `REDIS_STREAM_TTL_SECONDS` | TTL for stream keys (0 = no expiry) | `86400` (24 hours) |

### Database Migrations

This application uses **Alembic** for database schema management. The database schema is now versioned and managed through migration files.

#### Migration Commands

```bash
# Apply all pending migrations (required for first setup)
make migrate-db

# Create a new migration (for developers making schema changes)
cd server && python migrate.py revision "add user preferences table"
```

#### First Setup
When setting up the application for the first time:

1. Set up your PostgreSQL database (see above)
2. Run `make migrate-db` to create all tables
3. Start the application with `make dev-server`

#### Development Workflow
- The `make dev-server` command automatically runs migrations before starting the server
- All database schema changes must be done through migration files
- Never modify database schema directly in production

#### Creating New Migrations
When you need to modify the database schema:

1. **Create the migration file:**
   ```bash
   cd server
   python migrate.py revision "descriptive message about the change"
   ```

2. **Edit the generated migration file** in `server/database_migrations/versions/`
   - Add your SQL DDL statements in the `upgrade()` function
   - Use `op.execute("CREATE TABLE ...")` for raw SQL
   - Add corresponding DROP statements in `downgrade()` if needed

3. **Test the migration:**
   ```bash
   make migrate-db  # Apply the new migration
   ```

#### Migration Files
- Location: `server/database_migrations/versions/`
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
Add the following to your `server/.env` file:

```bash
# AWS S3 Configuration for File Uploads
AWS_ACCESS_KEY_ID="your_aws_access_key_id_here"
AWS_SECRET_ACCESS_KEY="your_aws_secret_access_key_here"
AWS_REGION="us-east-1"  # or your preferred region
AWS_S3_BUCKET_NAME="your_s3_bucket_name_here"
```


## Environment Variables

### Backend Configuration

Copy `server/env.example` to `server/.env` and fill in your values:

```bash
cp server/env.example server/.env
```

The `env.example` file is organized into sections with clear `[REQUIRED]` and `[OPTIONAL]` markers. Required variables will cause the server to crash at startup if missing.

**Key required variables:**
- `DATABASE_URL`, `DB_POOL_*` - PostgreSQL connection and pool settings
- `CLERK_SECRET_KEY`, `CLERK_PUBLISHABLE_KEY` - Authentication
- `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `XAI_API_KEY` - LLM providers
- `RUNPOD_API_KEY`, `RUNPOD_SSH_ACCESS_KEY`, `RUNPOD_SUPPORTED_GPUS` - GPU provisioning
- `AWS_*` - S3 file storage
- `STRIPE_*` - Billing
- `MIN_BALANCE_CENTS_FOR_*` - Billing limits
- `JSON_MODEL_PRICE_PER_MILLION_IN_CENTS` - LLM pricing
- `TELEMETRY_WEBHOOK_URL`, `HF_TOKEN`, `PIPELINE_MONITOR_*`, `PIPELINE_MAX_RESTART_ATTEMPTS` - Research pipeline
- `SERVER_AUTO_RELOAD`, `LOG_LEVEL`, `FRONTEND_URL`, `CORS_ORIGINS`, `CORS_CREDENTIALS` - Server config

See `server/env.example` for the complete list with descriptions.

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
- `.env` files are ignored by git for security
- `env.example` provides template with default values
- **Clerk credentials are required** - the server won't start without them

## Available Scripts

```bash
make dev-server                          # Start development server (with auto-migrations)
make install-server                      # Install dependencies
make lint-server                         # Run all linters
make migrate                             # Run database migrations
make export-openapi                      # Export OpenAPI schema
make gen-api-types                       # Generate TypeScript types for frontend
```

### Manual Python Commands
```bash
python -m uvicorn app.main:app --reload  # Start development server
python -m black .                        # Format Python code
python -m isort .                        # Sort Python imports
python -m ruff check .                   # Lint Python code
python -m mypy .                         # Type check Python code
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
    - `run-started`, heartbeats, stage progress (4 stages × 3 iterations), stage-completed, logs, and `run-finished`.
    - Token usage, hardware stats, figure reviews, and LLM review webhooks.
    - One small fake artifact uploaded to S3 and recorded in `rp_artifacts`.
  - Pod metadata uses `pod_id=fake-...`, `publicIp=127.0.0.1`, `portMappings={"22": "0"}` so readiness checks pass; SSH log upload is effectively skipped.

## API Type Generation

The frontend uses types generated directly from the server's OpenAPI schema. Do not define duplicate hand-written API types.

- Generate schema and types from file:
  ```bash
  make gen-api-types
  ```
  This exports `server/openapi.json` and writes `frontend/src/types/api.gen.ts`.

- Or generate directly from a running server:
  ```bash
  cd frontend && npm run gen:api-types
  ```

During builds, `prebuild` generates types from `server/openapi.json` to avoid drift.