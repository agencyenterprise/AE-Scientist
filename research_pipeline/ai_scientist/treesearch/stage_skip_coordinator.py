import logging
from typing import Iterable, Tuple

from . import execution_registry, stage_control
from .stage_identifiers import StageIdentifier

logger = logging.getLogger(__name__)


class SkipInProgressError(RuntimeError):
    """Raised when a skip is detected for the active stage."""

    def __init__(self, *, stage_identifier: StageIdentifier, reason: str) -> None:
        super().__init__(reason)
        self.stage_identifier = stage_identifier
        self.reason = reason

    @property
    def stage_name(self) -> str:
        return self.stage_identifier.prefixed_name


class StageSkipCoordinator:
    """Shared helper for interacting with stage skip control state."""

    def __init__(self, *, stage_identifier: StageIdentifier) -> None:
        self.stage_identifier = stage_identifier

    @property
    def stage_name(self) -> str:
        return self.stage_identifier.prefixed_name

    def ensure_no_skip_pending(self) -> None:
        """Raise if a skip request is currently pending for this stage."""
        state = stage_control.get_stage_state()
        if not state:
            return
        if state.get("skip_pending") and state.get("stage_name") == self.stage_name:
            reason = state.get("skip_reason") or "Stage skip requested by operator."
            logger.info(
                "Skip pending detected for stage %s (reason=%s)",
                self.stage_name,
                reason,
            )
            raise SkipInProgressError(stage_identifier=self.stage_identifier, reason=reason)

    def consume_pending_request(self) -> Tuple[bool, str | None]:
        """Consume any pending skip request for this stage and return (is_skip, reason)."""
        reason = stage_control.consume_skip_request(stage_name=self.stage_name)
        if reason is None:
            return False, None
        return True, reason

    def flag_executions_for_skip(self, execution_ids: Iterable[str], *, reason: str) -> int:
        """Mark executions for skip so workers exit early."""
        ids = [exec_id for exec_id in execution_ids if exec_id]
        if not ids:
            return 0
        logger.info(
            "Flagging %s active execution(s) for skip in stage %s (reason=%s)",
            len(ids),
            self.stage_name,
            reason,
        )
        for execution_id in ids:
            execution_registry.flag_skip_pending(
                execution_id=execution_id,
                reason=reason,
            )
        return len(ids)
