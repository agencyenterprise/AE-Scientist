"""Make pod_id, pod_name, and gpu_type NOT NULL in research_pipeline_runs.

Deletes rows where these columns are NULL (orphaned records from failed pod creation),
then adds NOT NULL constraints.

Revision ID: 0059
Revises: 0058
Create Date: 2026-02-06
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0059"
down_revision: Union[str, None] = "0058"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Delete rows where pod_id, pod_name, or gpu_type are NULL
    # These are orphaned records from failed pod creation attempts
    op.execute(
        """
        DELETE FROM research_pipeline_runs
        WHERE pod_id IS NULL
           OR pod_name IS NULL
           OR gpu_type IS NULL
    """
    )

    # Add NOT NULL constraints
    op.alter_column("research_pipeline_runs", "pod_id", nullable=False)
    op.alter_column("research_pipeline_runs", "pod_name", nullable=False)
    op.alter_column("research_pipeline_runs", "gpu_type", nullable=False)


def downgrade() -> None:
    # Remove NOT NULL constraints
    op.alter_column("research_pipeline_runs", "pod_id", nullable=True)
    op.alter_column("research_pipeline_runs", "pod_name", nullable=True)
    op.alter_column("research_pipeline_runs", "gpu_type", nullable=True)
