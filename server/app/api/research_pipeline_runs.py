import logging
from typing import Dict
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, status
from pydantic import BaseModel

from app.middleware.auth import get_current_user
from app.services import get_database
from app.services.database.ideas import IdeaData
from app.services.research_pipeline.runpod_launcher import RunPodError, launch_research_pipeline_run

router = APIRouter(prefix="/conversations", tags=["research-pipeline"])
logger = logging.getLogger(__name__)


class ResearchRunAcceptedResponse(BaseModel):
    run_id: str
    status: str = "ok"


def _idea_version_to_payload(idea_data: IdeaData) -> Dict[str, object]:
    experiments = idea_data.experiments or []
    risks = idea_data.risk_factors_and_limitations or []
    return {
        "Name": f"idea_{idea_data.idea_id}_v{idea_data.version_number}",
        "Title": idea_data.title or "",
        "Short Hypothesis": idea_data.short_hypothesis or "",
        "Related Work": idea_data.related_work or "",
        "Abstract": idea_data.abstract or "",
        "Experiments": experiments if isinstance(experiments, list) else [],
        "Expected Outcome": idea_data.expected_outcome or "",
        "Risk Factors and Limitations": risks if isinstance(risks, list) else [],
    }


def _launch_research_pipeline_job(*, run_id: str, idea_payload: Dict[str, object]) -> None:
    """Background task that launches the RunPod job and updates DB state."""
    db = get_database()
    config_name = f"{run_id}_config.yaml"
    try:
        logger.info("Launching research pipeline job in background for run_id=%s", run_id)
        pod_info = launch_research_pipeline_run(
            idea=idea_payload,
            config_name=config_name,
            run_id=run_id,
        )
        db.update_research_pipeline_run(run_id=run_id, pod_info=pod_info)
    except (RunPodError, FileNotFoundError, ValueError, RuntimeError) as exc:
        logger.exception("Failed to launch research pipeline run.")
        db.update_research_pipeline_run(run_id=run_id, status="failed", error_message=str(exc))
    else:
        logger.info("Background launch complete for run_id=%s", run_id)


@router.post(
    "/{conversation_id}/idea/research-run",
    response_model=ResearchRunAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def submit_idea_for_research(
    conversation_id: int,
    request: Request,
    background_tasks: BackgroundTasks,
) -> ResearchRunAcceptedResponse:
    if conversation_id <= 0:
        raise HTTPException(status_code=400, detail="conversation_id must be positive")

    user = get_current_user(request)
    db = get_database()

    conversation = db.get_conversation_by_id(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if conversation.user_id != user.id:
        raise HTTPException(status_code=403, detail="You do not own this conversation")

    idea_data = db.get_idea_by_conversation_id(conversation_id)
    if idea_data is None or idea_data.version_id is None:
        raise HTTPException(status_code=400, detail="Conversation does not have an active idea")

    run_id = f"rp-{uuid4().hex[:10]}"
    db.create_research_pipeline_run(
        run_id=run_id,
        idea_id=idea_data.idea_id,
        idea_version_id=idea_data.version_id,
    )

    idea_payload = _idea_version_to_payload(idea_data)
    background_tasks.add_task(
        _launch_research_pipeline_job,
        run_id=run_id,
        idea_payload=idea_payload,
    )

    return ResearchRunAcceptedResponse(run_id=run_id)
