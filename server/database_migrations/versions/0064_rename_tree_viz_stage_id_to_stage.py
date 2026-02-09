"""Rename stage_id to stage in rp_tree_viz and convert values.

Convert from "Stage_X" or "stage_X" format to StageId enum values:
- "Stage_1" / "stage_1" → "1_initial_implementation"
- "Stage_2" / "stage_2" → "2_baseline_tuning"
- "Stage_3" / "stage_3" → "3_creative_research"
- "Stage_4" / "stage_4" → "4_ablation_studies"

Revision ID: 0064
Revises: 0063
Create Date: 2025-02-09
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0064"
down_revision: Union[str, None] = "0063"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Rename stage_id column to stage and convert values to StageId format."""
    # First, convert the values from "Stage_X" / "stage_X" to StageId enum values
    op.execute(
        """
        UPDATE rp_tree_viz
        SET stage_id = CASE
            WHEN LOWER(stage_id) = 'stage_1' THEN '1_initial_implementation'
            WHEN LOWER(stage_id) = 'stage_2' THEN '2_baseline_tuning'
            WHEN LOWER(stage_id) = 'stage_3' THEN '3_creative_research'
            WHEN LOWER(stage_id) = 'stage_4' THEN '4_ablation_studies'
            ELSE stage_id  -- Keep as-is if already in new format
        END
        """
    )

    # Drop the old unique constraint
    op.drop_constraint("uq_rp_tree_viz_run_stage", "rp_tree_viz", type_="unique")

    # Rename the column
    op.alter_column("rp_tree_viz", "stage_id", new_column_name="stage")

    # Re-create the unique constraint with the new column name
    op.create_unique_constraint("uq_rp_tree_viz_run_stage", "rp_tree_viz", ["run_id", "stage"])


def downgrade() -> None:
    """Revert stage column back to stage_id and convert values back."""
    # Drop the new unique constraint
    op.drop_constraint("uq_rp_tree_viz_run_stage", "rp_tree_viz", type_="unique")

    # Rename the column back
    op.alter_column("rp_tree_viz", "stage", new_column_name="stage_id")

    # Re-create the unique constraint with the old column name
    op.create_unique_constraint("uq_rp_tree_viz_run_stage", "rp_tree_viz", ["run_id", "stage_id"])

    # Convert values back to "Stage_X" format
    op.execute(
        """
        UPDATE rp_tree_viz
        SET stage_id = CASE
            WHEN stage_id = '1_initial_implementation' THEN 'Stage_1'
            WHEN stage_id = '2_baseline_tuning' THEN 'Stage_2'
            WHEN stage_id = '3_creative_research' THEN 'Stage_3'
            WHEN stage_id = '4_ablation_studies' THEN 'Stage_4'
            ELSE stage_id  -- Keep as-is if not in new format
        END
        """
    )
