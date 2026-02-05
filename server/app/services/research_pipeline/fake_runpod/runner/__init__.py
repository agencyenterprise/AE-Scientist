"""FakeRunner sub-package combining mixins into a complete runner."""

from ..state import register_runner_factory
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


def _runner_factory(run_id: str, pod_id: str, webhook_url: str, webhook_token: str) -> FakeRunner:
    """Factory function for creating FakeRunner instances."""
    return FakeRunner(
        run_id=run_id,
        pod_id=pod_id,
        webhook_url=webhook_url,
        webhook_token=webhook_token,
    )


# Register the factory so server.py can create runners without importing this module
register_runner_factory(_runner_factory)


__all__ = ["FakeRunner"]
