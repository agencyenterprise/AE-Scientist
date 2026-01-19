from enum import Enum


class StageIdentifier(Enum):
    STAGE1 = (1, "initial_implementation")
    STAGE2 = (2, "baseline_tuning")
    STAGE3 = (3, "creative_research")
    STAGE4 = (4, "ablation_studies")

    def __init__(self, number: int, slug: str) -> None:
        self._number = number
        self._slug = slug

    @property
    def number(self) -> int:
        return self._number

    @property
    def slug(self) -> str:
        return self._slug

    @property
    def prefixed_name(self) -> str:
        return f"{self._number}_{self._slug}"

    @classmethod
    def ordered(cls) -> tuple["StageIdentifier", ...]:
        return tuple(cls)

    @classmethod
    def from_prefixed_name(cls, *, prefixed_name: str) -> "StageIdentifier | None":
        for identifier in cls:
            if identifier.prefixed_name == prefixed_name:
                return identifier
        return None

    def next_stage(self) -> "StageIdentifier | None":
        order = self.ordered()
        idx = order.index(self)
        if idx + 1 < len(order):
            return order[idx + 1]
        return None
