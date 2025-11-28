# SOP: Server Database Migrations

## Related Documentation
- [Server Architecture](../System/server_architecture.md)
- [Project Architecture](../System/project_architecture.md)

---

## Overview

This SOP covers creating and running database migrations using Alembic for the FastAPI server. Use this procedure when you need to:
- Add new database tables
- Modify existing table schemas
- Add indexes or constraints
- Update data types

---

## Prerequisites

- Python environment activated (`.venv`)
- PostgreSQL database running
- Environment variables configured (`POSTGRES_*` or `DATABASE_URL`)

---

## Step-by-Step Procedure

### 1. Check Current Migration Status

```bash
cd server
python migrate.py current
```

This shows the currently applied migration version.

### 2. Create a New Migration

```bash
python migrate.py revision "description_of_change"
```

This creates a new file in `database_migrations/versions/` with the naming pattern:
```
XXXX_description_of_change.py
```

### 3. Edit the Migration File

Open the newly created migration file and implement `upgrade()` and `downgrade()` functions:

```python
"""description_of_change

Revision ID: XXXX
Revises: YYYY
Create Date: 2024-XX-XX

"""
from alembic import op

# revision identifiers
revision = "XXXX"
down_revision = "YYYY"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply the migration."""
    op.execute("""
        CREATE TABLE IF NOT EXISTS new_table (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
        )
    """)


def downgrade() -> None:
    """Revert the migration."""
    op.execute("DROP TABLE IF EXISTS new_table")
```

### 4. Run the Migration

```bash
python migrate.py upgrade
```

### 5. Verify the Migration

```bash
python migrate.py current
python migrate.py history
```

---

## Key Files

| File | Purpose |
|------|---------|
| `server/migrate.py` | Migration CLI tool |
| `server/alembic.ini` | Alembic configuration |
| `server/database_migrations/env.py` | Migration environment setup |
| `server/database_migrations/versions/` | Migration scripts directory |

---

## Common Patterns

### Adding a Table

```python
def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS my_table (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            data JSONB NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
        )
    """)

def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS my_table")
```

### Adding an Index

```python
def upgrade() -> None:
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_my_table_user_id
        ON my_table(user_id)
    """)

def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_my_table_user_id")
```

### Adding a Column

```python
def upgrade() -> None:
    op.execute("""
        ALTER TABLE my_table
        ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'active'
    """)

def downgrade() -> None:
    op.execute("ALTER TABLE my_table DROP COLUMN IF EXISTS status")
```

### Adding Full-Text Search Index (pg_trgm)

```python
def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_my_table_name_trgm
        ON my_table USING gin(name gin_trgm_ops)
    """)
```

---

## Available Commands

| Command | Description |
|---------|-------------|
| `python migrate.py upgrade` | Apply all pending migrations |
| `python migrate.py current` | Show current migration version |
| `python migrate.py history` | Show migration history |
| `python migrate.py heads` | Show current head revisions |
| `python migrate.py revision "msg"` | Create a new migration |

---

## Common Pitfalls

- **Always include `downgrade()`**: Every migration must be reversible
- **Use `IF NOT EXISTS` / `IF EXISTS`**: Prevents errors on re-runs
- **Test locally first**: Run migrations on local database before deploying
- **Don't modify applied migrations**: Create new migrations for changes
- **Foreign key order**: Create parent tables before child tables with FK references

---

## Verification

After running a migration:

1. Check the migration was applied:
   ```bash
   python migrate.py current
   ```

2. Verify the schema change in PostgreSQL:
   ```bash
   psql -h localhost -U postgres -d your_db -c "\d my_table"
   ```

3. Test the server still starts:
   ```bash
   uv run uvicorn app.main:app --reload
   ```
