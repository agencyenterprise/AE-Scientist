import json
import logging
import os
import queue
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, NamedTuple

import uvicorn
from fastapi import Body, FastAPI, HTTPException, Query
from pydantic import BaseModel
from research_pipeline.ai_scientist.artifact_manager import (  # type: ignore[import-not-found]
    ArtifactPublisher,
    ArtifactSpec,
)
from research_pipeline.ai_scientist.telemetry.event_persistence import (  # type: ignore[import-not-found]
    EventPersistenceManager,
    PersistableEvent,
    WebhookClient,
)

logger = logging.getLogger(__name__)


class PodRecord(NamedTuple):
    id: str
    name: str
    gpu_type_requested: str
    desired_status: str
    public_ip: str
    port_mappings: Dict[str, str]
    cost_per_hr: float
    created_at: float
    ready_at: float
    run_id: str


class PodRequest(BaseModel):
    name: str
    imageName: str
    cloudType: str
    gpuCount: int
    gpuTypeIds: List[str]
    containerDiskInGb: int
    volumeInGb: int
    env: Dict[str, str]
    ports: List[str]
    dockerStartCmd: List[str]


class BillingRecord(NamedTuple):
    podId: str
    amount: float
    timeBilledMs: int


class TelemetryRecord(NamedTuple):
    path: str
    payload: Dict[str, object]
    received_at: float


app = FastAPI(title="Fake RunPod Server")
_pods: Dict[str, PodRecord] = {}
_lock = threading.Lock()
_telemetry_events: List[TelemetryRecord] = []


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"{name} is required for fake RunPod server")
    return value


def _build_pod_response(record: PodRecord) -> Dict[str, object]:
    return {
        "id": record.id,
        "name": record.name,
        "desiredStatus": record.desired_status,
        "publicIp": record.public_ip or None,
        "portMappings": record.port_mappings,
        "costPerHr": record.cost_per_hr,
        "gpu_type_requested": record.gpu_type_requested,
    }


def _schedule_ready_transition(record: PodRecord, delay_seconds: int) -> None:
    def _transition() -> None:
        time.sleep(delay_seconds)
        with _lock:
            current = _pods.get(record.id)
            if current is None:
                return
            updated = PodRecord(
                id=current.id,
                name=current.name,
                gpu_type_requested=current.gpu_type_requested,
                desired_status="RUNNING",
                public_ip="127.0.0.1",
                port_mappings={"22": "0"},
                cost_per_hr=current.cost_per_hr,
                created_at=current.created_at,
                ready_at=time.time(),
                run_id=current.run_id,
            )
            _pods[record.id] = updated

    thread = threading.Thread(target=_transition, name=f"fake-ready-{record.id}", daemon=True)
    thread.start()


def _start_fake_runner(
    *,
    record: PodRecord,
    webhook_url: str,
    webhook_token: str,
    db_url: str,
    aws_access_key_id: str,
    aws_secret_access_key: str,
    aws_region: str,
    aws_s3_bucket_name: str,
) -> None:
    runner = FakeRunner(
        run_id=record.run_id,
        pod_id=record.id,
        webhook_url=webhook_url,
        webhook_token=webhook_token,
        database_url=db_url,
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
        aws_region=aws_region,
        aws_s3_bucket_name=aws_s3_bucket_name,
    )
    thread = threading.Thread(target=runner.run, name=f"fake-runner-{record.run_id}", daemon=True)
    thread.start()


@app.post("/pods")
def create_pod(request: PodRequest = Body(...)) -> Dict[str, object]:
    if not request.gpuTypeIds:
        raise HTTPException(status_code=400, detail="gpuTypeIds required")
    run_id = request.env.get("RUN_ID")
    if not run_id:
        raise HTTPException(status_code=400, detail="RUN_ID env missing")
    aws_access_key_id = request.env.get("AWS_ACCESS_KEY_ID")
    aws_secret_access_key = request.env.get("AWS_SECRET_ACCESS_KEY")
    aws_region = request.env.get("AWS_REGION")
    aws_s3_bucket_name = request.env.get("AWS_S3_BUCKET_NAME")
    if (
        not aws_access_key_id
        or not aws_secret_access_key
        or not aws_region
        or not aws_s3_bucket_name
    ):
        raise HTTPException(status_code=400, detail="AWS_* env missing")
    pod_id = f"fake-{uuid.uuid4()}"
    created_at = time.time()
    record = PodRecord(
        id=pod_id,
        name=request.name,
        gpu_type_requested=request.gpuTypeIds[0],
        desired_status="PENDING",
        public_ip="",
        port_mappings={},
        cost_per_hr=0.0,
        created_at=created_at,
        ready_at=0.0,
        run_id=run_id,
    )
    with _lock:
        _pods[pod_id] = record
    _schedule_ready_transition(record, delay_seconds=1)
    webhook_url = _require_env("TELEMETRY_WEBHOOK_URL")
    webhook_token = _require_env("TELEMETRY_WEBHOOK_TOKEN")
    db_url = _require_env("DATABASE_PUBLIC_URL")
    _start_fake_runner(
        record=record,
        webhook_url=webhook_url,
        webhook_token=webhook_token,
        db_url=db_url,
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
        aws_region=aws_region,
        aws_s3_bucket_name=aws_s3_bucket_name,
    )
    return _build_pod_response(record)


@app.get("/pods/{pod_id}")
def get_pod(pod_id: str) -> Dict[str, object]:
    with _lock:
        record = _pods.get(pod_id)
    if record is None:
        raise HTTPException(status_code=404, detail="pod not found")
    return _build_pod_response(record)


@app.delete("/pods/{pod_id}")
def delete_pod(pod_id: str) -> Dict[str, str]:
    with _lock:
        _pods.pop(pod_id, None)
    return {"status": "deleted"}


@app.get("/billing/pods")
def get_billing_summary(
    podId: str = Query(...), grouping: str = Query(...)
) -> List[Dict[str, object]]:
    if grouping != "podId":
        raise HTTPException(status_code=400, detail="Unsupported grouping")
    with _lock:
        record = _pods.get(podId)
    if record is None:
        return []
    return [
        {
            "podId": record.id,
            "amount": 0.0,
            "timeBilledMs": 0,
        }
    ]


@app.post("/graphql")
def graphql_query(body: Dict[str, object] = Body(...)) -> Dict[str, object]:
    query = body.get("query")
    variables = body.get("variables", {})
    if "podHostId" in json.dumps(query):
        return {"data": {"pod": {"machine": {"podHostId": "fake-host"}}}}
    return {"data": {}, "variables": variables}


@app.post("/telemetry/run-started", status_code=204)
def telemetry_run_started(payload: Dict[str, object] = Body(...)) -> None:
    _telemetry_events.append(
        TelemetryRecord(path="/telemetry/run-started", payload=payload, received_at=time.time())
    )


@app.post("/telemetry/run-finished", status_code=204)
def telemetry_run_finished(payload: Dict[str, object] = Body(...)) -> None:
    _telemetry_events.append(
        TelemetryRecord(path="/telemetry/run-finished", payload=payload, received_at=time.time())
    )


@app.post("/telemetry/heartbeat", status_code=204)
def telemetry_heartbeat(payload: Dict[str, object] = Body(...)) -> None:
    _telemetry_events.append(
        TelemetryRecord(path="/telemetry/heartbeat", payload=payload, received_at=time.time())
    )


@app.post("/telemetry/stage-progress", status_code=204)
def telemetry_stage_progress(payload: Dict[str, object] = Body(...)) -> None:
    _telemetry_events.append(
        TelemetryRecord(path="/telemetry/stage-progress", payload=payload, received_at=time.time())
    )


@app.post("/telemetry/substage-completed", status_code=204)
def telemetry_substage(payload: Dict[str, object] = Body(...)) -> None:
    _telemetry_events.append(
        TelemetryRecord(
            path="/telemetry/substage-completed", payload=payload, received_at=time.time()
        )
    )


@app.post("/telemetry/gpu-shortage", status_code=204)
def telemetry_gpu_shortage(payload: Dict[str, object] = Body(...)) -> None:
    _telemetry_events.append(
        TelemetryRecord(path="/telemetry/gpu-shortage", payload=payload, received_at=time.time())
    )


@app.post("/telemetry/paper-generation-progress", status_code=204)
def telemetry_paper_generation_progress(payload: Dict[str, object] = Body(...)) -> None:
    _telemetry_events.append(
        TelemetryRecord(
            path="/telemetry/paper-generation-progress", payload=payload, received_at=time.time()
        )
    )


@app.get("/telemetry")
def list_telemetry() -> List[Dict[str, object]]:
    return [
        {
            "path": record.path,
            "payload": record.payload,
            "received_at": record.received_at,
        }
        for record in _telemetry_events
    ]


class LocalPersistence:
    def __init__(self, webhook_client: object) -> None:
        self.queue: "queue.SimpleQueue[PersistableEvent | None]" = queue.SimpleQueue()
        self._webhook_client = webhook_client

    def start(self) -> None:
        return

    def stop(self) -> None:
        return


class FakeRunner:
    def __init__(
        self,
        run_id: str,
        pod_id: str,
        webhook_url: str,
        webhook_token: str,
        database_url: str,
        aws_access_key_id: str,
        aws_secret_access_key: str,
        aws_region: str,
        aws_s3_bucket_name: str,
    ) -> None:
        self._run_id = run_id
        self._pod_id = pod_id
        self._webhook_url = webhook_url
        self._webhook_token = webhook_token
        self._database_url = database_url
        self._aws_access_key_id = aws_access_key_id
        self._aws_secret_access_key = aws_secret_access_key
        self._aws_region = aws_region
        self._aws_s3_bucket_name = aws_s3_bucket_name
        self._iterations_per_stage = 3
        self._stage_plan: list[tuple[str, int]] = [
            ("1_initial_implementation_1_preliminary", 10),
            ("2_baseline_tuning_1_first_attempt", 5),
            ("3_creative_research_1_first_attempt", 5),
            ("4_ablation_studies_1_first_attempt", 5),
        ]
        self._heartbeat_interval_seconds = 10
        webhook_client = WebhookClient(
            base_url=self._webhook_url,
            token=self._webhook_token,
            run_id=self._run_id,
        )
        try:
            self._persistence = EventPersistenceManager(
                database_url=self._database_url,
                run_id=self._run_id,
                webhook_client=webhook_client,
                queue_maxsize=1024,
            )
        except Exception:
            logger.exception("Falling back to local persistence for run %s", self._run_id)
            self._persistence = LocalPersistence(webhook_client)
        self._webhook_client: Any = getattr(self._persistence, "_webhook_client", None)
        self._heartbeat_stop = threading.Event()

    def run(self) -> None:
        logger.info(
            "[FakeRunner %s] Starting simulation for pod %s", self._run_id[:8], self._pod_id[:13]
        )
        self._persistence.start()
        self._publish_run_started()
        heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop, name=f"heartbeat-{self._run_id}", daemon=True
        )
        heartbeat_thread.start()
        logger.info(
            "[FakeRunner %s] Heartbeat thread started (interval=%ds)",
            self._run_id[:8],
            self._heartbeat_interval_seconds,
        )
        try:
            self._emit_progress_flow()
            self._publish_fake_artifact()
            self._publish_run_finished(True, "")
        finally:
            self._heartbeat_stop.set()
            heartbeat_thread.join(timeout=self._heartbeat_interval_seconds + 1)
            self._persistence.stop()
            logger.info("[FakeRunner %s] Simulation complete", self._run_id[:8])

    def _heartbeat_loop(self) -> None:
        webhook_client = self._webhook_client
        while not self._heartbeat_stop.is_set():
            self._persistence.queue.put(
                PersistableEvent(kind="run_log", data={"message": "heartbeat", "level": "debug"})
            )
            try:
                if webhook_client is not None:
                    webhook_client.publish_heartbeat()
            except Exception:
                logger.exception("Failed to publish heartbeat for run %s", self._run_id)
            self._heartbeat_stop.wait(timeout=self._heartbeat_interval_seconds)

    def _emit_progress_flow(self) -> None:
        total_iterations = len(self._stage_plan) * self._iterations_per_stage
        current_iter = 0
        for stage_index, (stage_name, max_iterations) in enumerate(self._stage_plan):
            logger.info(
                "[FakeRunner %s] Stage %d/%d: %s",
                self._run_id[:8],
                stage_index + 1,
                len(self._stage_plan),
                stage_name,
            )
            iterations_to_emit = min(self._iterations_per_stage, max_iterations)
            for iteration in range(iterations_to_emit):
                current_iter += 1
                progress = (iteration + 1) / max_iterations
                self._persistence.queue.put(
                    PersistableEvent(
                        kind="run_stage_progress",
                        data={
                            "stage": stage_name,
                            "iteration": iteration + 1,
                            "max_iterations": max_iterations,
                            "progress": progress,
                            "total_nodes": 10 + iteration,
                            "buggy_nodes": iteration,
                            "good_nodes": 9 - iteration,
                            "best_metric": f"metric-{progress:.2f}",
                            "eta_s": int((total_iterations - current_iter) * 20),
                            "latest_iteration_time_s": 20,
                        },
                    )
                )
                self._persistence.queue.put(
                    PersistableEvent(
                        kind="run_log",
                        data={
                            "message": f"{stage_name} iteration {iteration + 1} complete",
                            "level": "info",
                        },
                    )
                )
                time.sleep(20)
                logger.info(
                    "[FakeRunner %s]   Iteration %d/%d complete (%.0f%% overall)",
                    self._run_id[:8],
                    iteration + 1,
                    iterations_to_emit,
                    (current_iter / total_iterations) * 100,
                )
            summary = {
                "goals": f"Goals for {stage_name}",
                "feedback": "Reached max iterations",
                "good_nodes": 2,
                "best_metric": f"Metrics(fake metric for {stage_name})",
                "buggy_nodes": 1,
                "total_nodes": 3,
            }
            self._persistence.queue.put(
                PersistableEvent(
                    kind="substage_completed",
                    data={
                        "stage": stage_name,
                        "main_stage_number": stage_index + 1,
                        "substage_number": 1,
                        "substage_name": "fake-substage",
                        "reason": "completed",
                        "summary": summary,
                    },
                )
            )
            logger.info(
                "[FakeRunner %s] Stage %d/%d complete",
                self._run_id[:8],
                stage_index + 1,
                len(self._stage_plan),
            )

        # Stage 5: Paper Generation
        logger.info("[FakeRunner %s] Starting paper generation (Stage 5)", self._run_id[:8])
        self._emit_paper_generation_flow()

    def _emit_paper_generation_flow(self) -> None:
        """Emit Stage 5 paper generation progress events."""
        # Define the paper generation steps with their substeps
        paper_steps: list[tuple[str, list[str], dict[str, object]]] = [
            (
                "plot_aggregation",
                ["collecting_figures", "validating_plots", "generating_captions"],
                {"figures_collected": 8, "valid_plots": 7},
            ),
            (
                "citation_gathering",
                ["searching_literature", "filtering_relevant", "formatting_citations"],
                {"citations_found": 15, "relevant_citations": 12},
            ),
            (
                "paper_writeup",
                [
                    "writing_abstract",
                    "writing_introduction",
                    "writing_methodology",
                    "writing_results",
                    "writing_discussion",
                    "writing_conclusion",
                ],
                {"sections_completed": 6, "word_count": 4500},
            ),
            (
                "paper_review",
                ["review_1", "review_2", "review_3"],
                {
                    "avg_score": 7.2,
                    "review_scores": [7.0, 7.5, 7.1],
                    "strengths": ["novel approach", "thorough experiments"],
                    "weaknesses": ["limited comparison", "minor clarity issues"],
                },
            ),
        ]

        total_steps = len(paper_steps)
        for step_idx, (step_name, substeps, step_details) in enumerate(paper_steps):
            logger.info(
                "[FakeRunner %s] Paper step %d/%d: %s",
                self._run_id[:8],
                step_idx + 1,
                total_steps,
                step_name,
            )
            for substep_idx, substep_name in enumerate(substeps):
                step_progress = (substep_idx + 1) / len(substeps)
                overall_progress = (step_idx + step_progress) / total_steps

                self._persistence.queue.put(
                    PersistableEvent(
                        kind="paper_generation_progress",
                        data={
                            "step": step_name,
                            "substep": substep_name,
                            "progress": overall_progress,
                            "step_progress": step_progress,
                            "details": {
                                **step_details,
                                "current_substep": substep_idx + 1,
                                "total_substeps": len(substeps),
                            },
                        },
                    )
                )
                self._persistence.queue.put(
                    PersistableEvent(
                        kind="run_log",
                        data={
                            "message": f"Paper generation: {step_name} - {substep_name}",
                            "level": "info",
                        },
                    )
                )
                # Shorter delay for paper generation steps (5s instead of 20s)
                time.sleep(5)
                logger.info(
                    "[FakeRunner %s]   %s complete (%.0f%% step)",
                    self._run_id[:8],
                    substep_name,
                    step_progress * 100,
                )

        # Log completion
        self._persistence.queue.put(
            PersistableEvent(
                kind="run_log",
                data={
                    "message": "Paper generation completed",
                    "level": "info",
                },
            )
        )
        logger.info("[FakeRunner %s] Paper generation complete", self._run_id[:8])

    def _publish_fake_artifact(self) -> None:
        temp_dir = Path(os.environ.get("TMPDIR") or "/tmp")
        artifact_path = temp_dir / f"{self._run_id}-fake-result.txt"
        artifact_path.write_text("fake run output\n", encoding="utf-8")
        publisher = ArtifactPublisher(
            run_id=self._run_id,
            aws_access_key_id=self._aws_access_key_id,
            aws_secret_access_key=self._aws_secret_access_key,
            aws_region=self._aws_region,
            aws_s3_bucket_name=self._aws_s3_bucket_name,
            database_url=self._database_url,
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

    def _publish_run_started(self) -> None:
        try:
            if self._webhook_client is not None:
                self._webhook_client.publish_run_started()
        except Exception:
            logger.exception("Failed to publish run-started for %s", self._run_id)

    def _publish_run_finished(self, success: bool, message: str) -> None:
        try:
            if self._webhook_client is not None:
                self._webhook_client.publish_run_finished(
                    success=success,
                    message=message,
                )
        except Exception:
            logger.exception("Failed to publish run-finished for %s", self._run_id)


def main() -> None:
    port_value = _require_env("FAKE_RUNPOD_PORT")
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=int(port_value),
        log_level="info",
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
