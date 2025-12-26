"""Ensure rp_artifacts.s3_key is unique.

Revision ID: 0027
Revises: 0026
Create Date: 2025-12-26
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0027"
down_revision: Union[str, None] = "0026"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        WITH ranked AS (
            SELECT
                id,
                ROW_NUMBER() OVER (
                    PARTITION BY s3_key
                    ORDER BY created_at DESC, id DESC
                ) AS rn
            FROM rp_artifacts
        )
        DELETE FROM rp_artifacts
        WHERE id IN (SELECT id FROM ranked WHERE rn > 1);
        """
    )
    op.create_unique_constraint(
        "uq_rp_artifacts_s3_key",
        "rp_artifacts",
        ["s3_key"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_rp_artifacts_s3_key", "rp_artifacts", type_="unique")
