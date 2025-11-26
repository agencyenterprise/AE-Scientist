from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, Tuple

from ..events import BaseEvent
from ..journal import Journal, Node
from ..utils.config import Config


@dataclass
class StageMeta:
    name: str
    number: int
    slug: str
    substage_number: int
    substage_name: str
    goals: str
    max_iterations: int
    num_drafts: int


@dataclass
class StageContext:
    cfg: Config
    task_desc: str
    stage_name: str
    journal: Journal
    workspace_dir: Path
    event_callback: Callable[[BaseEvent], None]
    best_nodes_by_stage: Dict[int, Node]


class Stage:
    def __init__(self, *, meta: StageMeta, context: StageContext) -> None:
        self._meta = meta
        self._context = context

    def meta(self) -> StageMeta:
        return self._meta

    def context(self) -> StageContext:
        return self._context

    def prepare_substage(self) -> bool:
        return True

    def evaluate_substage_completion(self) -> Tuple[bool, str]:
        raise NotImplementedError

    def evaluate_stage_completion(self) -> Tuple[bool, str]:
        raise NotImplementedError

    def best_carryover_nodes(self) -> Dict[int, Node]:
        return self._context.best_nodes_by_stage
