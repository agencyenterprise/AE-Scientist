from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Tuple

from pydantic import BaseModel

from ..config import Config
from ..events import BaseEvent
from ..journal import Journal
from ..stage_identifiers import StageIdentifier


class StageCompletionEvaluation(BaseModel):
    is_complete: bool
    reasoning: str
    missing_criteria: List[str]


@dataclass
class StageMeta:
    identifier: StageIdentifier
    goals: str
    max_iterations: int
    num_drafts: int

    @property
    def number(self) -> int:
        return self.identifier.number

    @property
    def name(self) -> str:
        return self.identifier.prefixed_name


@dataclass
class StageContext:
    cfg: Config
    task_desc: str
    stage_identifier: StageIdentifier
    journal: Journal
    workspace_dir: Path
    event_callback: Callable[[BaseEvent], None]

    @property
    def stage_name(self) -> str:
        return self.stage_identifier.prefixed_name


class Stage:
    def __init__(self, *, meta: StageMeta, context: StageContext) -> None:
        self._meta = meta
        self._context = context
        self._stage_identifier = meta.identifier
        self.can_be_skipped: bool = False
        self.skip_reason: str = "Stage cannot be skipped yet."

    def meta(self) -> StageMeta:
        return self._meta

    def context(self) -> StageContext:
        return self._context

    @property
    def stage_identifier(self) -> StageIdentifier:
        return self._stage_identifier

    def evaluate_substage_completion(self) -> Tuple[bool, str]:
        raise NotImplementedError

    def evaluate_stage_completion(self) -> Tuple[bool, str]:
        raise NotImplementedError

    def reset_skip_state(self) -> None:
        """Reset can_be_skipped + reason state."""
        self.can_be_skipped = False
        self.skip_reason = "Stage cannot be skipped yet."

    def skip_state(self) -> Tuple[bool, str]:
        return self.can_be_skipped, self.skip_reason

    def _set_skip_state(self, *, can_skip: bool, reason: str) -> None:
        self.can_be_skipped = can_skip
        self.skip_reason = reason
