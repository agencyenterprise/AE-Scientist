"""
Launches the research pipeline on RunPod and injects refined ideas/configurations.
"""

import asyncio
import logging
import math
from typing import Any, NamedTuple, cast

import httpx

from app.config import settings

from .code_packager import get_code_tarball_info
from .runpod_initialization import (
    CONTAINER_DISK_GB,
    WORKSPACE_DISK_GB,
    build_remote_script,
    encode_multiline,
    get_pod_name,
    load_runpod_environment,
    prepare_config_text,
)

logger = logging.getLogger(__name__)

DEFAULT_STARTUP_GRACE_SECONDS = 600
POD_READY_POLL_INTERVAL_SECONDS = 5

DEFAULT_RUNPOD_DATACENTER_IDS: tuple[str, ...] = (
    # RunPod published dataCenterIds options (full list), ordered by proximity to AWS us-east-1 (N. Virginia).
    #
    # Heuristic ordering:
    # - US East (closest)
    # - US Central
    # - US West
    # - Canada East
    # - Europe
    # - APAC / Oceania (farthest)
    "US-DE-1",
    "US-NC-1",
    "US-GA-1",
    "US-GA-2",
    "US-IL-1",
    "US-KS-2",
    "US-KS-3",
    "US-TX-1",
    "US-TX-3",
    "US-TX-4",
    "US-CA-2",
    "US-WA-1",
    "CA-MTL-1",
    "CA-MTL-2",
    "CA-MTL-3",
    "EU-NL-1",
    "EU-FR-1",
    "EU-SE-1",
    "EU-CZ-1",
    "EU-RO-1",
    "EUR-NO-1",
    "EUR-IS-1",
    "EUR-IS-2",
    "EUR-IS-3",
    "AP-JP-1",
    "OC-AU-1",
)


def _safe_float(value: float | int | str | None) -> float | None:
    if isinstance(value, (int, float, str)):
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
    return None


def _safe_int(value: int | float | str | None) -> int | None:
    if isinstance(value, (int, float, str)):
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
    return None


class RunPodError(Exception):
    """RunPod API error"""

    def __init__(self, message: str, status: int = 0):
        super().__init__(message)
        self.status = status


class PodLaunchInfo(NamedTuple):
    pod_id: str
    pod_name: str
    gpu_type: str
    cost: float


class PodReadyMetadata(NamedTuple):
    public_ip: str
    ssh_port: str
    pod_host_id: str


class PodBillingRecord(NamedTuple):
    amount: float | None
    timeBilledMs: int | None
    diskSpaceBilledGB: int | None
    podId: str | None
    time: str | None


class PodBillingSummary(NamedTuple):
    pod_id: str
    total_amount_usd: float
    time_billed_ms: int
    record_count: int
    records: list[PodBillingRecord]


class RunPodManager:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = settings.runpod.fake_base_url or "https://rest.runpod.io/v1"
        self.graphql_url = settings.runpod.fake_graphql_url or "https://api.runpod.io/graphql"

    async def _make_request(
        self,
        endpoint: str,
        method: str = "GET",
        data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any] | list[dict[str, Any]]:
        url = f"{self.base_url}{endpoint}"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                json=data,
            )
            if response.is_error:
                raise RunPodError(
                    f"RunPod API error ({response.status_code}): {response.text}",
                    status=response.status_code,
                )
            if response.status_code == 204 or not response.content:
                return {}
            payload = response.json()
            if isinstance(payload, dict):
                return cast(dict[str, Any], payload)
            if isinstance(payload, list):
                return [cast(dict[str, Any], item) for item in payload]
            raise RunPodError(
                f"Unexpected RunPod response format for {endpoint}: {payload}",
                status=response.status_code,
            )

    async def _graphql_request(self, query: str, variables: dict[str, Any]) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                self.graphql_url,
                headers=headers,
                json={"query": query, "variables": variables},
            )
        if response.is_error:
            raise RunPodError(
                f"GraphQL error ({response.status_code}): {response.text}",
                status=response.status_code,
            )
        return cast(dict[str, Any], response.json())

    async def get_pod_host_id(self, pod_id: str) -> str | None:
        query = """
            query pod($input: PodFilter!) {
                pod(input: $input) {
                    machine {
                        podHostId
                    }
                }
            }
        """
        variables = {"input": {"podId": pod_id}}
        try:
            result = await self._graphql_request(query=query, variables=variables)
            machine = cast(dict[str, Any], result.get("data", {}).get("pod", {}).get("machine", {}))
            return machine.get("podHostId")
        except (RunPodError, httpx.HTTPError, ValueError):
            return None

    async def _attempt_create_pod(
        self,
        *,
        name: str,
        image: str,
        gpu_type: str,
        pod_env: dict[str, str],
        docker_cmd: str,
    ) -> dict[str, Any]:
        datacenter_ids = list(DEFAULT_RUNPOD_DATACENTER_IDS)
        payload = {
            "name": name,
            "imageName": image,
            "cloudType": "SECURE",
            "gpuCount": 1,
            "gpuTypeIds": [gpu_type],
            "dataCenterIds": datacenter_ids,
            "dataCenterPriority": "custom",
            "containerDiskInGb": CONTAINER_DISK_GB,
            "volumeInGb": WORKSPACE_DISK_GB,
            "env": pod_env,
            "ports": ["22/tcp"],
            "dockerStartCmd": ["bash", "-c", docker_cmd],
        }
        response = await self._make_request(endpoint="/pods", method="POST", data=payload)
        if not isinstance(response, dict):
            raise RunPodError("Unexpected response while creating pod.", status=0)
        return response

    async def create_pod(
        self,
        *,
        name: str,
        image: str,
        gpu_types: list[str],
        pod_env: dict[str, str],
        docker_cmd: str,
        max_retries: int = 3,
    ) -> dict[str, Any]:
        if not gpu_types:
            raise ValueError("At least one GPU type must be specified")

        last_error: Exception | None = None
        max_attempts = max(max_retries, len(gpu_types))

        for i in range(max_attempts):
            gpu_type = gpu_types[i % len(gpu_types)]
            try:
                pod = await self._attempt_create_pod(
                    name=name,
                    image=image,
                    gpu_type=gpu_type,
                    pod_env=pod_env,
                    docker_cmd=docker_cmd,
                )
                return pod
            except RunPodError as error:
                last_error = error
                unavailable = (
                    "no instances currently available" in str(error).lower() or error.status == 500
                )
                if not unavailable or i == max_attempts - 1:
                    raise
                await asyncio.sleep(1)
        raise RunPodError(
            f"Failed to create pod after {max_attempts} attempts. "
            f"Tried GPU types: {', '.join(gpu_types)}. "
            f"Last error: {last_error}"
        )

    async def get_pod(self, pod_id: str) -> dict[str, Any]:
        response = await self._make_request(endpoint=f"/pods/{pod_id}")
        if not isinstance(response, dict):
            raise RunPodError("Unexpected response while retrieving pod.", status=0)
        return response

    async def delete_pod(self, pod_id: str) -> None:
        await self._make_request(endpoint=f"/pods/{pod_id}", method="DELETE", data=None)

    async def get_pod_billing_summary(self, pod_id: str) -> PodBillingSummary | None:
        params = {"podId": pod_id, "grouping": "podId"}
        response = await self._make_request(endpoint="/billing/pods", method="GET", params=params)
        if not isinstance(response, list):
            raise RunPodError("Unexpected billing response format.", status=0)
        logger.debug("Billing response: %s", response)
        if not response:
            logger.info("No billing records returned for pod %s; skipping summary.", pod_id)
            return None
        records_raw = response
        total_amount = 0.0
        total_ms = 0
        filtered_records: list[PodBillingRecord] = []

        for record in records_raw:
            record_pod_id = cast(str | None, record.get("podId"))
            if record_pod_id and record_pod_id != pod_id:
                continue

            amount_raw = cast(float | int | str | None, record.get("amount"))
            amount_value = _safe_float(amount_raw)
            if amount_value is not None:
                total_amount += amount_value

            billed_ms_raw = cast(int | float | str | None, record.get("timeBilledMs"))
            billed_ms = _safe_int(billed_ms_raw)
            if billed_ms is not None:
                total_ms += billed_ms

            filtered_records.append(
                PodBillingRecord(
                    amount=amount_value,
                    timeBilledMs=billed_ms,
                    diskSpaceBilledGB=_safe_int(
                        cast(int | float | str | None, record.get("diskSpaceBilledGB"))
                    ),
                    podId=record_pod_id,
                    time=cast(str | None, record.get("time")),
                )
            )
        return PodBillingSummary(
            pod_id=pod_id,
            total_amount_usd=round(total_amount, 6),
            time_billed_ms=total_ms,
            record_count=len(filtered_records),
            records=filtered_records,
        )

    async def wait_for_pod_ready(
        self, *, pod_id: str, poll_interval: int = 5, max_attempts: int = 60
    ) -> dict[str, Any]:
        for _ in range(max_attempts):
            await asyncio.sleep(poll_interval)
            pod = await self.get_pod(pod_id=pod_id)
            is_running = pod.get("desiredStatus") == "RUNNING"
            has_public_ip = pod.get("publicIp") is not None
            has_port_mappings = bool(pod.get("portMappings", {}))
            if is_running and has_public_ip and has_port_mappings:
                return pod
        raise RunPodError("Pod did not become ready in time")


def get_pipeline_startup_grace_seconds() -> int:
    return max(settings.research_pipeline.monitor_startup_grace_seconds, 1)


def get_supported_gpu_types() -> list[str]:
    """Return the GPU types that can be targeted when launching RunPod jobs."""
    return list(settings.runpod.supported_gpus)


async def launch_research_pipeline_run(
    *,
    title: str,
    idea: str,
    config_name: str,
    run_id: str,
    requested_by_first_name: str,
    gpu_types: list[str],
    parent_run_id: str | None,
    webhook_token: str,
) -> PodLaunchInfo:
    env = load_runpod_environment()

    idea_filename = f"{run_id}_idea.txt"
    config_filename = config_name
    telemetry_block: dict[str, str] = {
        "run_id": run_id,
        "webhook_url": env.telemetry_webhook_url,
        "webhook_token": webhook_token,
    }
    logger.info(
        "Launching research pipeline run_id=%s with config=%s (telemetry url=%s)",
        run_id,
        config_filename,
        env.telemetry_webhook_url,
    )

    idea_text = idea
    config_text = prepare_config_text(
        title=title, idea_filename=idea_filename, telemetry=telemetry_block
    )
    idea_b64 = encode_multiline(idea_text)
    config_b64 = encode_multiline(config_text)

    # Get code tarball info (URL and commit hash)
    tarball_info = get_code_tarball_info()

    docker_cmd = build_remote_script(
        env=env,
        idea_filename=idea_filename,
        idea_content_b64=idea_b64,
        config_filename=config_filename,
        config_content_b64=config_b64,
        run_id=run_id,
        has_previous_run=True if parent_run_id else False,
        webhook_token=webhook_token,
        commit_hash=tarball_info.commit_hash,
    )

    creator = RunPodManager(api_key=settings.runpod.api_key)

    pod_env = {
        "CODE_TARBALL_URL": tarball_info.url,
    }
    if parent_run_id:
        pod_env["HAS_PREVIOUS_RUN"] = "true"
        pod_env["PARENT_RUN_ID"] = parent_run_id
    if not gpu_types:
        raise ValueError("At least one GPU type must be provided when launching a pod.")
    pod_name = get_pod_name(user_name=requested_by_first_name, run_id=run_id)
    pod = await creator.create_pod(
        name=pod_name,
        image="newtonsander/runpod_pytorch_texdeps:v1.1",
        gpu_types=gpu_types,
        pod_env=pod_env,
        docker_cmd=docker_cmd,
    )
    logger.debug("Pod created: %s", pod)
    return PodLaunchInfo(
        pod_id=pod["id"],
        pod_name=cast(str, pod.get("name")),
        gpu_type=cast(str, pod.get("machine", {}).get("gpuTypeId")),
        cost=cast(float, pod.get("costPerHr")),
    )


async def fetch_pod_ready_metadata(*, pod_id: str) -> PodReadyMetadata:
    manager = RunPodManager(api_key=settings.runpod.api_key)
    poll_interval_seconds = POD_READY_POLL_INTERVAL_SECONDS
    startup_grace_seconds = get_pipeline_startup_grace_seconds()
    max_attempts = max(1, math.ceil(startup_grace_seconds / poll_interval_seconds))
    ready_pod = await manager.wait_for_pod_ready(
        pod_id=pod_id,
        poll_interval=poll_interval_seconds,
        max_attempts=max_attempts,
    )
    pod_host_id = await manager.get_pod_host_id(pod_id=pod_id)
    return PodReadyMetadata(
        public_ip=cast(str, ready_pod.get("publicIp")),
        ssh_port=cast(str, ready_pod.get("portMappings", {}).get("22")),
        pod_host_id=cast(str, pod_host_id),
    )


async def terminate_pod(*, pod_id: str) -> None:
    creator = RunPodManager(api_key=settings.runpod.api_key)
    try:
        logger.info("Terminating RunPod pod %s...", pod_id)
        await creator.delete_pod(pod_id=pod_id)
        logger.info("Terminated RunPod pod %s.", pod_id)
    except RunPodError as exc:
        logger.warning("Failed to terminate RunPod pod %s: %s", pod_id, exc)
        raise RuntimeError(f"Failed to terminate pod {pod_id}: {exc}") from exc


async def fetch_pod_billing_summary(*, pod_id: str) -> PodBillingSummary | None:
    manager = RunPodManager(api_key=settings.runpod.api_key)
    return await manager.get_pod_billing_summary(pod_id=pod_id)
