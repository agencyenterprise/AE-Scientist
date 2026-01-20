from typing import Literal, cast

from app.api.research_pipeline_stream import publish_stream_event
from app.models.sse import ResearchRunTerminationStatusData, ResearchRunTerminationStatusEvent
from app.services.database.research_pipeline_runs import ResearchPipelineRunTermination


def build_termination_status_payload(
    *,
    termination: ResearchPipelineRunTermination | None,
) -> dict[str, object]:
    if termination is None:
        return {"status": "none", "last_error": None}

    return {
        "status": termination.status,
        "last_error": termination.last_error,
    }


def publish_termination_status_event(
    *,
    run_id: str,
    termination: ResearchPipelineRunTermination | None,
) -> None:
    data = build_termination_status_payload(termination=termination)
    publish_stream_event(
        run_id,
        ResearchRunTerminationStatusEvent(
            type="termination_status",
            data=ResearchRunTerminationStatusData(
                status=cast(
                    Literal["none", "requested", "in_progress", "terminated", "failed"],
                    data["status"],
                ),
                last_error=cast(str | None, data.get("last_error")),
            ),
        ),
    )
