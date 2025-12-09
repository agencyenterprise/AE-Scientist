# AE Scientist - Server

A collaborative platform that transforms LLM conversations into structured research ideas through AI-guided refinement.

## How It Works

**AE Scientist** streamlines the journey from conversational ideas to structured project execution:

1. **Import Conversations**: Paste LLM share URLs to import rich conversational content that contains research ideas, technical discussions, or experimental concepts.

2. **Generate Research Ideas**: AI analyzes the imported conversations and automatically generates structured research proposals with hypotheses, experiments, and expected outcomes.

3. **Refine Through Dialogue**: Engage in an interactive refinement process where you can prompt the AI to adjust, expand, or focus the research scope. Ask for more experimental detail, refine hypotheses, or explore different methodologies.



### Setup

1. **Set up Google OAuth (REQUIRED)**
   
   Create a Google OAuth application for user authentication:
   
   a. Go to [Google Cloud Console](https://console.cloud.google.com/)
   b. Create/select a project
   c. Enable Google+ API (APIs & Services → Library)
   d. Create OAuth 2.0 credentials (APIs & Services → Credentials)
      - Application type: Web application
      - Authorized redirect URIs: `http://localhost:8000/api/auth/callback`
      - Authorized JavaScript origins: `http://localhost:3000`
   e. Configure domain restrictions for your organization (OAuth consent screen)
   f. Copy your Client ID and Client Secret

2. **Environment Configuration**
   ```bash
   # Copy environment templates
   cp server/env.example server/.env
   cp frontend/env.local.example frontend/.env.local
   
   # IMPORTANT: Edit server/.env with your Google OAuth credentials
   ```

3. **Setup using Makefile (Recommended)**
   ```bash
   # Install all dependencies (creates virtual environment automatically)
   make install
   
   # Start development servers
   make dev-server    # Starts FastAPI server using virtual environment
   make dev-frontend   # Starts Next.js server
   ```

   **🔒 First Run**: Visit `http://localhost:3000` → You'll be redirected to login page → Sign in with Google!

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

### Playwright Setup

Playwright is used for browser automation in the backend (e.g., scraping and browser-driven tests). After installing backend dependencies, install the browser binaries locally.

```bash
# Install Playwright browsers inside the backend virtualenv
cd backend
. .venv/bin/activate  # or use your preferred venv activation
python -m playwright install firefox

# Verify installation
python -m playwright --version
```

Docker users: the backend image installs Firefox via Playwright during build, so no additional setup is required inside the container.

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

# Run all tests
make test
```

## Available Scripts

### Makefile Commands
```bash
make help            # Show all available commands
make venv-backend    # Create Python virtual environment
make lint            # Lint both frontend and backend
make lint-frontend   # Lint frontend code only
make lint-backend    # Lint backend code (uses venv)
make format          # Format both frontend and backend code
make format-frontend # Format frontend code only
make format-backend  # Format backend code (uses venv)
make install         # Install all dependencies
make dev-frontend    # Start frontend development server
make dev-backend     # Start backend development server (uses venv)
make migrate-db      # Apply all pending database migrations
make create-test-db  # Create fresh test database and apply migrations
make test-backend    # Run backend tests with isolated test database
make test            # Run all tests
```

## Environment Variables

### Backend Configuration

Copy `backend/env.example` to `backend/.env` and customize as needed:

```bash
# Database Configuration (PostgreSQL - REQUIRED)
DATABASE_URL="postgresql://ae_scientist_user:your_password@localhost:5432/ae_scientist"
POSTGRES_USER="ae_scientist_user"
POSTGRES_PASSWORD="your_password"

# Google OAuth Configuration (REQUIRED for authentication)
GOOGLE_CLIENT_ID="your-google-oauth-client-id-here"
GOOGLE_CLIENT_SECRET="your-google-oauth-client-secret-here"
GOOGLE_REDIRECT_URI="http://localhost:8000/api/auth/callback"

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

# Research pipeline telemetry (optional webhooks from the experiment runner)
TELEMETRY_WEBHOOK_URL="https://your-backend-host/api/research-pipeline/events"
TELEMETRY_WEBHOOK_TOKEN="your_shared_secret_token"
HF_TOKEN="your_huggingface_token"

# Research pipeline monitor settings (all required)
PIPELINE_MONITOR_POLL_INTERVAL_SECONDS="60"
PIPELINE_MONITOR_HEARTBEAT_TIMEOUT_SECONDS="60"
PIPELINE_MONITOR_MAX_MISSED_HEARTBEATS="5"
PIPELINE_MONITOR_STARTUP_GRACE_SECONDS="600"
RUN_POD_SSH_ACCESS_KEY="-----BEGIN OPENSSH PRIVATE KEY-----\n...replace...\n-----END OPENSSH PRIVATE KEY-----"

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

This application now requires **Google OAuth 2.0 authentication** for all users.

### User Authentication Flow
1. Users visit the application and are redirected to `/login`
2. Click "Sign in with Google" to authenticate via OAuth 2.0
3. Google validates the user and redirects back to the application
4. Users can access all features and their session persists for 24 hours
5. Users can sign out at any time from the dashboard header

### Security Features
- Organization-only access (configured in Google OAuth console)
- HTTP-only secure session cookies
- Automatic session expiration and cleanup
- Protected API endpoints (all routes except `/health`, `/docs`, `/auth/*`)

**Important:**
- `.env` and `.env.local` files are ignored by git for security
- `env.example` files provide templates with default values
- **Google OAuth credentials are required** - the app won't start without them
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