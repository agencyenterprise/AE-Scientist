"""Add disk capacity columns to research_pipeline_runs.

Revision ID: 0031
Revises: 0030
Create Date: 2025-12-30
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0031"
down_revision: Union[str, None] = "0030"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_DEFAULT_CONTAINER_DISK_GB = 100
_DEFAULT_VOLUME_DISK_GB = 200


def upgrade() -> None:
    """Store container and volume capacities per research run."""
    op.add_column(
        "research_pipeline_runs",
        sa.Column("container_disk_gb", sa.Integer(), nullable=True),
    )
    op.add_column(
        "research_pipeline_runs",
        sa.Column("volume_disk_gb", sa.Integer(), nullable=True),
    )
    op.execute(
        sa.text(
            """
            UPDATE research_pipeline_runs
            SET container_disk_gb = :container_gb,
                volume_disk_gb = :volume_gb
            WHERE container_disk_gb IS NULL AND volume_disk_gb IS NULL
            """
        ).bindparams(
            container_gb=_DEFAULT_CONTAINER_DISK_GB,
            volume_gb=_DEFAULT_VOLUME_DISK_GB,
        )
    )


def downgrade() -> None:
    """Drop disk capacity tracking columns."""
    op.drop_column("research_pipeline_runs", "volume_disk_gb")
    op.drop_column("research_pipeline_runs", "container_disk_gb")
