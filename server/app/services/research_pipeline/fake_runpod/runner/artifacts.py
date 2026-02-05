"""Artifact publishing methods for FakeRunner."""

import json
import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

# fmt: off
# isort: off
from research_pipeline.ai_scientist.api_types import (  # type: ignore[import-not-found]
    TreeVizStoredEvent,
)
# isort: on
# fmt: on
from research_pipeline.ai_scientist.artifact_manager import (  # type: ignore[import-not-found]
    ArtifactPublisher,
    ArtifactSpec,
)

if TYPE_CHECKING:
    from .core import FakeRunnerCore

logger = logging.getLogger(__name__)


class ArtifactsMixin:
    """Mixin providing artifact publishing methods for FakeRunner."""

    # Type hints for methods/attributes from FakeRunnerCore
    _run_id: str
    _webhook_url: str
    _webhook_token: str
    _webhook_client: Any
    _webhooks: "FakeRunnerCore._webhooks"  # type: ignore[name-defined]
    _data_dir: Path
    _plot_filename: str | None

    def _publish_fake_artifact(self) -> None:
        """Publish a fake result artifact."""
        temp_dir = Path(os.environ.get("TMPDIR") or "/tmp")
        artifact_path = temp_dir / f"{self._run_id}-fake-result.txt"
        artifact_path.write_text("fake run output\n", encoding="utf-8")
        logger.info("Uploading fake artifact %s", artifact_path)
        publisher = ArtifactPublisher(
            run_id=self._run_id,
            webhook_base_url=self._webhook_url,
            webhook_token=self._webhook_token,
            webhook_client=self._webhook_client,
        )
        spec = ArtifactSpec(
            artifact_type="fake_result",
            path=artifact_path,
            packaging="file",
            archive_name=None,
            exclude_dir_names=tuple(),
        )
        try:
            publisher.publish(spec=spec)
            logger.info("[FakeRunner %s] Artifact published to S3", self._run_id[:8])
        except Exception:
            logger.exception("Failed to publish fake artifact for run %s", self._run_id)
        finally:
            publisher.close()
        try:
            artifact_path.unlink()
        except OSError:
            logger.warning("Failed to delete temp artifact %s", artifact_path)

    def _publish_fake_plot_artifact(self) -> None:
        """Publish a fake plot artifact."""
        plot_path = self._data_dir / "loss_curves.png"
        if not plot_path.exists():
            logger.warning("Fake plot not found at %s; skipping plot upload", plot_path)
            return
        logger.info("Uploading fake plot artifact %s", plot_path)
        publisher = ArtifactPublisher(
            run_id=self._run_id,
            webhook_base_url=self._webhook_url,
            webhook_token=self._webhook_token,
            webhook_client=self._webhook_client,
        )
        spec = ArtifactSpec(
            artifact_type="plot",
            path=plot_path,
            packaging="file",
            archive_name=None,
            exclude_dir_names=tuple(),
        )
        try:
            publisher.publish(spec=spec)
            self._plot_filename = plot_path.name
        except Exception:
            logger.exception("Failed to publish fake plot artifact for run %s", self._run_id)
        finally:
            publisher.close()

    def _store_tree_viz(self, *, stage_number: int, version: int = 1) -> None:
        """Store fake tree visualization data."""
        stage_id = f"Stage_{stage_number}"
        data_path = self._data_dir / f"stage_{stage_number}_tree_data.json"
        if not data_path.exists():
            logger.warning("Fake tree viz data not found for %s at %s", stage_id, data_path)
            return
        logger.info("Storing fake tree viz for %s from %s", stage_id, data_path)
        with data_path.open("r", encoding="utf-8") as f:
            payload = json.load(f)

        n_nodes = len(payload.get("layout") or payload.get("code") or [])
        if n_nodes > 0:
            # Inject fake Codex task markdown per node (for UI testing).
            codex_task = payload.get("codex_task")
            if not isinstance(codex_task, list) or len(codex_task) != n_nodes:
                codex_task = ["" for _ in range(n_nodes)]
            for idx in range(n_nodes):
                codex_task[idx] = "\n".join(
                    [
                        "# Codex task (fake)",
                        "",
                        f"- stage: {stage_id}",
                        f"- node_index: {idx}",
                        f"- version: {version}",
                        "",
                        "## Instructions",
                        "Write code for this node based on the context.",
                        "",
                        "## Context",
                        "This is synthetic data produced by the fake runner.",
                        "",
                    ]
                )
            payload["codex_task"] = codex_task

        if self._plot_filename:
            if n_nodes > 0:
                plots = payload.get("plots")
                if not isinstance(plots, list) or len(plots) != n_nodes:
                    plots = [[] for _ in range(n_nodes)]
                plots[0] = [self._plot_filename]
                payload["plots"] = plots
                plot_paths = payload.get("plot_paths")
                if not isinstance(plot_paths, list) or len(plot_paths) != n_nodes:
                    plot_paths = [[] for _ in range(n_nodes)]
                plot_paths[0] = [self._plot_filename]
                payload["plot_paths"] = plot_paths
                logger.debug(
                    "Injected plot %s into node 0 plots/plot_paths for %s",
                    self._plot_filename,
                    stage_id,
                )

        # Publish tree_viz_stored event via webhook (server will generate ID and persist to DB)
        try:
            self._webhooks.publish_tree_viz_stored(
                TreeVizStoredEvent(
                    stage_id=stage_id,
                    version=version,
                    viz=payload,  # Include full viz data in webhook
                )
            )
            logger.info(
                "Posted tree_viz_stored webhook: run=%s stage=%s",
                self._run_id,
                stage_id,
            )
        except Exception:  # noqa: BLE001 - fake runner best-effort
            logger.exception(
                "Failed to post tree_viz_stored webhook for run=%s stage=%s",
                self._run_id,
                stage_id,
            )
