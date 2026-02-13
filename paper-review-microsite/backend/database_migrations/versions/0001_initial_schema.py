"""Initial schema for AE Paper Review

Revision ID: 0001
Revises:
Create Date: 2024-01-01 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Users table (simplified - no billing)
    op.execute("""
        CREATE TABLE users (
            id SERIAL PRIMARY KEY,
            clerk_user_id VARCHAR(255) UNIQUE,
            email VARCHAR(255) UNIQUE NOT NULL,
            name VARCHAR(255) NOT NULL,
            is_active BOOLEAN DEFAULT TRUE NOT NULL,
            created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
            updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
        )
    """)
    op.execute("CREATE INDEX idx_users_clerk_user_id ON users(clerk_user_id)")
    op.execute("CREATE INDEX idx_users_email ON users(email)")

    # User sessions table
    op.execute("""
        CREATE TABLE user_sessions (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            session_token VARCHAR(255) UNIQUE NOT NULL,
            expires_at TIMESTAMPTZ NOT NULL,
            created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
        )
    """)
    op.execute("CREATE INDEX idx_user_sessions_token ON user_sessions(session_token)")
    op.execute("CREATE INDEX idx_user_sessions_user_id ON user_sessions(user_id)")
    op.execute("CREATE INDEX idx_user_sessions_expires_at ON user_sessions(expires_at)")

    # Paper reviews table
    op.execute("""
        CREATE TABLE paper_reviews (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            status VARCHAR(20) DEFAULT 'pending' NOT NULL,
            summary TEXT DEFAULT '' NOT NULL,
            strengths JSONB,
            weaknesses JSONB,
            originality INTEGER,
            quality INTEGER,
            clarity INTEGER,
            significance INTEGER,
            soundness INTEGER,
            presentation INTEGER,
            contribution INTEGER,
            overall INTEGER,
            confidence INTEGER,
            questions JSONB,
            limitations JSONB,
            ethical_concerns BOOLEAN,
            ethical_concerns_explanation TEXT DEFAULT '' NOT NULL,
            decision VARCHAR(50),
            original_filename VARCHAR(255) NOT NULL,
            s3_key VARCHAR(512),
            model VARCHAR(100) NOT NULL,
            error_message TEXT,
            progress REAL DEFAULT 0.0 NOT NULL,
            progress_step VARCHAR(255) DEFAULT '' NOT NULL,
            created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
        )
    """)
    op.execute("CREATE INDEX idx_paper_reviews_user_id ON paper_reviews(user_id)")
    op.execute("CREATE INDEX idx_paper_reviews_status ON paper_reviews(status)")
    op.execute("CREATE INDEX idx_paper_reviews_created_at ON paper_reviews(created_at DESC)")

    # Paper review token usages table
    op.execute("""
        CREATE TABLE paper_review_token_usages (
            id SERIAL PRIMARY KEY,
            paper_review_id INTEGER NOT NULL REFERENCES paper_reviews(id) ON DELETE CASCADE,
            provider VARCHAR(50) NOT NULL,
            model VARCHAR(100) NOT NULL,
            input_tokens INTEGER NOT NULL,
            cached_input_tokens INTEGER DEFAULT 0 NOT NULL,
            output_tokens INTEGER NOT NULL,
            created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
        )
    """)
    op.execute(
        "CREATE INDEX idx_token_usages_review_id ON paper_review_token_usages(paper_review_id)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS paper_review_token_usages CASCADE")
    op.execute("DROP TABLE IF EXISTS paper_reviews CASCADE")
    op.execute("DROP TABLE IF EXISTS user_sessions CASCADE")
    op.execute("DROP TABLE IF EXISTS users CASCADE")
