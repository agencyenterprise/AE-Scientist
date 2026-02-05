"""Authentication and authorization helpers for research pipeline webhooks."""

import hashlib
from datetime import datetime
from typing import Dict, Optional, Protocol, cast

from fastapi import Header, HTTPException, status

from app.api.research_pipeline.utils import REQUESTER_NAME_FALLBACK, extract_user_first_name
from app.services import get_database
from app.services.database.ideas import IdeaVersionData
from app.services.database.research_pipeline_run_termination import ResearchPipelineRunTermination
from app.services.database.research_pipeline_runs import PodUpdateInfo, ResearchPipelineRun
from app.services.database.users import UserData


class ResearchRunStore(Protocol):
    """Protocol defining the database interface for research run operations."""

    async def get_research_pipeline_run(self, run_id: str) -> Optional[ResearchPipelineRun]: ...

    async def get_run_webhook_token_hash(self, run_id: str) -> Optional[str]: ...

    async def update_research_pipeline_run(
        self,
        *,
        run_id: str,
        status: Optional[str] = None,
        initialization_status: Optional[str] = None,
        pod_update_info: Optional[PodUpdateInfo] = None,
        error_message: Optional[str] = None,
        last_heartbeat_at: Optional[datetime] = None,
        heartbeat_failures: Optional[int] = None,
        start_deadline_at: Optional[datetime] = None,
        last_billed_at: Optional[datetime] = None,
        started_running_at: Optional[datetime] = None,
    ) -> None: ...

    async def insert_research_pipeline_run_event(
        self,
        *,
        run_id: str,
        event_type: str,
        metadata: Dict[str, object],
        occurred_at: datetime,
    ) -> None: ...

    async def enqueue_research_pipeline_run_termination(
        self,
        *,
        run_id: str,
        trigger: str,
    ) -> ResearchPipelineRunTermination: ...

    async def get_run_owner_user_id(self, run_id: str) -> Optional[int]: ...

    async def get_user_by_id(self, user_id: int) -> Optional[UserData]: ...

    async def get_idea_version_by_id(self, idea_version_id: int) -> Optional[IdeaVersionData]: ...

    async def get_conversation_parent_run_id(self, conversation_id: int) -> Optional[str]: ...


async def _verify_run_token(run_id: str, token: str) -> None:
    """Verify the bearer token for a specific run.

    Validates against the per-run token hash stored in the database.
    """
    db = cast(ResearchRunStore, get_database())
    stored_hash = await db.get_run_webhook_token_hash(run_id)

    if stored_hash is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No token configured for this run.",
        )

    provided_hash = hashlib.sha256(token.encode()).hexdigest()
    if provided_hash != stored_hash:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization token.",
        )


async def verify_run_auth(
    run_id: str,
    authorization: str = Header(...),
) -> None:
    """FastAPI dependency that extracts and verifies the bearer token for a run.

    This combines token extraction and verification into a single dependency,
    eliminating the need for separate _extract_bearer_token and _verify_run_token calls.

    Usage:
        @router.post("/{run_id}/endpoint")
        async def my_endpoint(
            run_id: str,
            _: None = Depends(verify_run_auth),
        ) -> None:
            ...
    """
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format.",
        )
    await _verify_run_token(run_id, token)


async def resolve_run_owner_first_name(*, db: ResearchRunStore, run_id: str) -> str:
    """Get the first name of the run owner for personalization."""
    owner_id = await db.get_run_owner_user_id(run_id=run_id)
    if owner_id is None:
        return REQUESTER_NAME_FALLBACK
    user = await db.get_user_by_id(user_id=owner_id)
    if user is None:
        return REQUESTER_NAME_FALLBACK
    return extract_user_first_name(full_name=user.name)
