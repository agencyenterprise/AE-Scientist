"""
API endpoints for listing all research pipeline runs.
"""

import logging
from typing import Dict

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from app.middleware.auth import get_current_user
from app.models import ResearchRunListItem, ResearchRunListResponse
from app.models.conversations import ModelCost
from app.services import get_database
from app.services.cost_calculator import calculate_llm_token_usage_cost

router = APIRouter(prefix="/research-runs", tags=["research-runs"])
logger = logging.getLogger(__name__)


class ResearchRunCostResponse(BaseModel):
    total_cost: float
    cost_by_model: list[ModelCost]


def _row_to_list_item(row: dict) -> ResearchRunListItem:
    """Convert a database row to a ResearchRunListItem."""
    return ResearchRunListItem(
        run_id=row["run_id"],
        status=row["status"],
        idea_title=row["idea_title"] or "Untitled",
        idea_hypothesis=row.get("idea_hypothesis"),
        current_stage=row.get("current_stage"),
        progress=row.get("progress"),
        gpu_type=row.get("gpu_type"),
        cost=float(row["cost"]),
        best_metric=row.get("best_metric"),
        created_by_name=row["created_by_name"],
        created_at=row["created_at"].isoformat(),
        updated_at=row["updated_at"].isoformat(),
        artifacts_count=row.get("artifacts_count", 0),
        error_message=row.get("error_message"),
        conversation_id=row["conversation_id"],
    )


@router.get("/", response_model=ResearchRunListResponse)
def list_research_runs(
    request: Request,
    limit: int = Query(50, ge=1, le=500, description="Maximum number of runs to return"),
    offset: int = Query(0, ge=0, description="Number of runs to skip"),
    search: str = Query(None, description="Search term for run ID, title, hypothesis, or creator"),
    status: str = Query(None, description="Filter by status (pending, running, completed, failed)"),
) -> ResearchRunListResponse:
    """
    List research pipeline runs for the current user.

    Returns runs ordered by creation date (newest first) with:
    - Run metadata (status, GPU, timestamps)
    - Idea information (title, hypothesis)
    - Latest stage progress (stage, progress percentage, best metric)
    - Artifact count
    - Creator information

    Supports filtering by search term and status.
    """
    user = get_current_user(request)

    db = get_database()
    rows, total = db.list_all_research_pipeline_runs(
        limit=limit,
        offset=offset,
        search=search,
        status=status,
        user_id=user.id,
    )

    items = [_row_to_list_item(row) for row in rows]

    return ResearchRunListResponse(items=items, total=total)


@router.get("/{run_id}/", response_model=ResearchRunListItem)
def get_research_run(request: Request, run_id: str) -> ResearchRunListItem:
    """
    Get a single research pipeline run by run_id.

    Returns the run with enriched data including:
    - Run metadata (status, GPU, timestamps)
    - Idea information (title, hypothesis)
    - Latest stage progress (stage, progress percentage, best metric)
    - Artifact count
    - Creator information
    - conversation_id for navigation
    """
    get_current_user(request)

    db = get_database()
    row = db.get_enriched_research_pipeline_run(run_id)

    if not row:
        raise HTTPException(status_code=404, detail="Research run not found")

    return _row_to_list_item(row)


@router.get("/{run_id}/costs", response_model=ResearchRunCostResponse)
def get_research_run_costs(request: Request, run_id: str) -> ResearchRunCostResponse:
    """
    Get the cost breakdown for a specific research run.
    """
    get_current_user(request)

    db = get_database()
    token_usages = db.get_llm_token_usages_by_run_aggregated_by_model(run_id)
    token_usage_costs = calculate_llm_token_usage_cost(token_usages)

    total_cost = sum([cost.input_cost + cost.output_cost for cost in token_usage_costs])

    cost_by_model: Dict[str, ModelCost] = {}
    for cost in token_usage_costs:
        if cost.model not in cost_by_model:
            cost_by_model[cost.model] = ModelCost(
                model=cost.model, cost=cost.input_cost + cost.output_cost
            )
        else:
            cost_by_model[cost.model].cost += cost.input_cost + cost.output_cost

    return ResearchRunCostResponse(
        total_cost=total_cost,
        cost_by_model=list(cost_by_model.values()),
    )
