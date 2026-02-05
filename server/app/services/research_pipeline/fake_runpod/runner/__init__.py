"""FakeRunner sub-package combining mixins into a complete runner."""

from .artifacts import ArtifactsMixin
from .core import FakeRunnerCore
from .events import EventsMixin
from .fake_data import FakeDataMixin


class FakeRunner(
    FakeDataMixin,
    ArtifactsMixin,
    EventsMixin,
    FakeRunnerCore,
):
    """Fake runner for local testing that simulates a research pipeline.

    This class combines multiple mixins to provide:
    - Core lifecycle management (FakeRunnerCore)
    - Event emission (EventsMixin)
    - Artifact publishing (ArtifactsMixin)
    - Fake data generation (FakeDataMixin)
    """

    pass


__all__ = ["FakeRunner"]
