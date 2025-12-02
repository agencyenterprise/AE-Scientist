"""
Launches the research pipeline on RunPod and injects refined ideas/configurations.
"""

import base64
import json
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, cast

import requests
from omegaconf import OmegaConf


class RunPodError(Exception):
    """RunPod API error"""

    def __init__(self, message: str, status: int = 0):
        super().__init__(message)
        self.status = status


class RunPodCreator:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://rest.runpod.io/v1"
        self.graphql_url = "https://api.runpod.io/graphql"
        self._session = requests.Session()

    def _make_request(
        self, endpoint: str, method: str = "GET", data: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        url = f"{self.base_url}{endpoint}"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        response = requests.request(method=method, url=url, headers=headers, json=data, timeout=60)
        if not response.ok:
            raise RunPodError(
                f"RunPod API error ({response.status_code}): {response.text}",
                status=response.status_code,
            )
        if response.status_code == 204 or not response.content:
            return {}
        result = cast(dict[str, Any], response.json())
        return result

    def _graphql_request(self, query: str, variables: dict[str, Any]) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        response = requests.post(
            self.graphql_url,
            headers=headers,
            json={"query": query, "variables": variables},
            timeout=60,
        )
        if not response.ok:
            raise RunPodError(
                f"GraphQL error ({response.status_code}): {response.text}",
                status=response.status_code,
            )
        return cast(dict[str, Any], response.json())

    def get_pod_host_id(self, pod_id: str) -> str | None:
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
            result = self._graphql_request(query=query, variables=variables)
            machine = cast(dict[str, Any], result.get("data", {}).get("pod", {}).get("machine", {}))
            return machine.get("podHostId")
        except (RunPodError, requests.RequestException, ValueError):
            return None

    def _attempt_create_pod(
        self,
        *,
        name: str,
        image: str,
        gpu_type: str,
        env: dict[str, str],
        docker_cmd: str,
    ) -> dict[str, Any]:
        payload = {
            "name": name,
            "imageName": image,
            "cloudType": "SECURE",
            "gpuCount": 1,
            "gpuTypeIds": [gpu_type],
            "containerDiskInGb": 30,
            "volumeInGb": 70,
            "env": env,
            "ports": ["22/tcp"],
            "dockerStartCmd": ["bash", "-c", docker_cmd],
        }
        return self._make_request(endpoint="/pods", method="POST", data=payload)

    def create_pod(
        self,
        *,
        name: str,
        image: str,
        gpu_types: list[str],
        env: dict[str, str],
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
                pod = self._attempt_create_pod(
                    name=name,
                    image=image,
                    gpu_type=gpu_type,
                    env=env,
                    docker_cmd=docker_cmd,
                )
                pod["gpu_type_requested"] = gpu_type
                return pod
            except RunPodError as error:
                last_error = error
                unavailable = (
                    "no instances currently available" in str(error).lower() or error.status == 500
                )
                if not unavailable or i == max_attempts - 1:
                    raise
                time.sleep(1)
        raise RunPodError(
            f"Failed to create pod after {max_attempts} attempts. "
            f"Tried GPU types: {', '.join(gpu_types)}. "
            f"Last error: {last_error}"
        )

    def get_pod(self, pod_id: str) -> dict[str, Any]:
        return self._make_request(endpoint=f"/pods/{pod_id}")

    def stop_pod(self, pod_id: str) -> None:
        self._make_request(endpoint=f"/pods/{pod_id}", method="DELETE", data=None)

    def wait_for_pod_ready(
        self, *, pod_id: str, poll_interval: int = 5, max_attempts: int = 60
    ) -> dict[str, Any]:
        for _ in range(max_attempts):
            time.sleep(poll_interval)
            pod = self.get_pod(pod_id=pod_id)
            is_running = pod.get("desiredStatus") == "RUNNING"
            has_public_ip = pod.get("publicIp") is not None
            has_port_mappings = bool(pod.get("portMappings", {}))
            if is_running and has_public_ip and has_port_mappings:
                return pod
        raise RunPodError("Pod did not become ready in time")


@dataclass
class RunPodEnvironment:
    git_deploy_key: str
    openai_api_key: str
    hf_token: str
    database_public_url: str
    telemetry_webhook_url: str
    telemetry_webhook_token: str
    aws_access_key_id: str
    aws_secret_access_key: str
    aws_region: str
    aws_s3_bucket_name: str


logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[4]
CONFIG_TEMPLATE_PATH = Path(__file__).resolve().parent / "bfts_config_template.yaml"
RUNPOD_SETUP_SCRIPT_PATH = Path(__file__).resolve().parent / "runpod_repo_setup.sh"
RUNPOD_INSTALL_SCRIPT_PATH = Path(__file__).resolve().parent / "install_run_pod.sh"


def _load_repo_setup_script() -> str:
    if not RUNPOD_SETUP_SCRIPT_PATH.exists():
        raise RuntimeError(
            f"RunPod setup script missing at {RUNPOD_SETUP_SCRIPT_PATH}. "
            "Ensure server/app/services/research_pipeline/runpod_repo_setup.sh exists."
        )
    return RUNPOD_SETUP_SCRIPT_PATH.read_text(encoding="utf-8").strip()


def _load_runpod_environment() -> RunPodEnvironment:
    def _require(name: str) -> str:
        value = os.environ.get(name)
        if not value:
            raise RuntimeError(f"Environment variable {name} is required to launch RunPod.")
        return value

    return RunPodEnvironment(
        git_deploy_key=_require("GIT_DEPLOY_KEY").replace("\\n", "\n"),
        openai_api_key=_require("OPENAI_API_KEY"),
        hf_token=_require("HF_TOKEN"),
        database_public_url=_require("DATABASE_PUBLIC_URL"),
        telemetry_webhook_url=_require("TELEMETRY_WEBHOOK_URL"),
        telemetry_webhook_token=_require("TELEMETRY_WEBHOOK_TOKEN"),
        aws_access_key_id=_require("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=_require("AWS_SECRET_ACCESS_KEY"),
        aws_region=_require("AWS_REGION"),
        aws_s3_bucket_name=_require("AWS_S3_BUCKET_NAME"),
    )


def _prepare_config_text(*, idea_filename: str, telemetry: dict[str, str]) -> str:
    if not CONFIG_TEMPLATE_PATH.exists():
        raise RuntimeError(
            "Pipeline config template missing at "
            f"{CONFIG_TEMPLATE_PATH}. Ensure the file exists."
        )
    config = OmegaConf.load(CONFIG_TEMPLATE_PATH)
    logger.info(
        "Preparing pipeline config from %s with desc_file=%s",
        CONFIG_TEMPLATE_PATH,
        idea_filename,
    )
    config.desc_file = idea_filename
    if telemetry:
        config.telemetry = telemetry
    else:
        config.telemetry = None
    config_yaml = OmegaConf.to_yaml(config)
    if not config_yaml.endswith("\n"):
        config_yaml += "\n"
    return config_yaml


def _encode_multiline(value: str) -> str:
    return base64.b64encode(value.encode("utf-8")).decode("utf-8")


def _repository_setup_commands() -> list[str]:
    script_text = _load_repo_setup_script()
    return [
        "# === Repository Setup ===",
        "cat <<'RUNPOD_SETUP' | bash",
        script_text,
        "RUNPOD_SETUP",
        "",
    ]


def _load_install_script() -> str:
    if not RUNPOD_INSTALL_SCRIPT_PATH.exists():
        raise RuntimeError(
            f"RunPod install script missing at {RUNPOD_INSTALL_SCRIPT_PATH}. "
            "Ensure server/app/services/research_pipeline/install_run_pod.sh exists."
        )
    return RUNPOD_INSTALL_SCRIPT_PATH.read_text(encoding="utf-8").strip()


def _installation_commands() -> list[str]:
    script_text = _load_install_script()
    return [
        "# === Installation ===",
        'echo "Running installation script..."',
        "cd /workspace/AE-Scientist",
        "cat <<'RUNPOD_INSTALL' | bash",
        script_text,
        "RUNPOD_INSTALL",
        "",
    ]


def _build_remote_script(
    *,
    env: RunPodEnvironment,
    idea_filename: str,
    idea_content_b64: str,
    config_filename: str,
    config_content_b64: str,
    run_id: str,
) -> str:
    script_parts: list[str] = ["set -euo pipefail", ""]
    script_parts += [
        "# === GPU Validation ===",
        'echo "Validating GPU..."',
        'nvidia-smi || { echo "❌ nvidia-smi failed"; exit 1; }',
        'echo "✅ GPU validated"',
        "",
    ]
    script_parts += _repository_setup_commands()
    script_parts += _installation_commands()
    script_parts += [
        "# === Environment Setup ===",
        'echo "Creating .env file..."',
        "cd /workspace/AE-Scientist/research_pipeline",
        "cat > .env << 'EOF'",
        f"OPENAI_API_KEY={env.openai_api_key}",
        f"HF_TOKEN={env.hf_token}",
        f"AWS_ACCESS_KEY_ID={env.aws_access_key_id}",
        f"AWS_SECRET_ACCESS_KEY={env.aws_secret_access_key}",
        f"AWS_REGION={env.aws_region}",
        f"AWS_S3_BUCKET_NAME={env.aws_s3_bucket_name}",
        f"RUN_ID={run_id}",
        f"DATABASE_PUBLIC_URL={env.database_public_url}",
        "EOF",
        "# === Inject refined idea and config ===",
        "cd /workspace/AE-Scientist/research_pipeline",
        "python - <<'PY'",
        "import base64, pathlib",
        f"pathlib.Path('{idea_filename}').write_bytes(base64.b64decode('{idea_content_b64}'))",
        f"pathlib.Path('{config_filename}').write_bytes(base64.b64decode('{config_content_b64}'))",
        "PY",
        "",
        "# === Starting Research Pipeline ===",
        'echo "Launching research pipeline..."',
        "source .venv/bin/activate",
        "pipeline_exit_code=0",
        "set +e",
        f"python launch_scientist_bfts.py '{config_filename}' 2>&1 | tee -a /workspace/research_pipeline.log",
        "pipeline_exit_code=$?",
        "set -e",
        'if [ "$pipeline_exit_code" -eq 0 ]; then',
        '  echo "Research pipeline completed successfully. Check /workspace/research_pipeline.log for full output."',
        "else",
        '  echo "Research pipeline failed. Check /workspace/research_pipeline.log for details."',
        "fi",
        "",
        "# === Upload Research Pipeline Log to S3 ===",
        'echo "Uploading research pipeline log to S3 (best-effort)..."',
        "python upload_runpod_log.py --log-path /workspace/research_pipeline.log --artifact-type run_log || true",
        'if [ "$pipeline_exit_code" -ne 0 ]; then',
        '  echo "Research pipeline failed with exit code $pipeline_exit_code (log uploaded)."',
        "  python upload_runpod_workspace.py --workspace-path /workspace/AE-Scientist/workspaces/0-run --artifact-type workspace_archive --archive-name 0-run-workspace.zip || true",
        "else",
        '  echo "Research pipeline finished successfully (log uploaded)."',
        "fi",
    ]
    return "\n".join(script_parts).strip()


def launch_research_pipeline_run(
    *,
    idea: Dict[str, Any],
    config_name: str,
    run_id: str,
) -> Dict[str, Any]:
    runpod_api_key = os.environ.get("RUNPOD_API_KEY")
    if not runpod_api_key:
        raise RuntimeError("RUNPOD_API_KEY environment variable is required.")
    env = _load_runpod_environment()

    idea_filename = f"{run_id}_idea.json"
    config_filename = config_name
    telemetry_block: dict[str, str] = {
        "database_url": env.database_public_url,
        "run_id": run_id,
        "webhook_url": env.telemetry_webhook_url,
        "webhook_token": env.telemetry_webhook_token,
    }
    logger.info(
        "Launching research pipeline run_id=%s with config=%s (telemetry url=%s)",
        run_id,
        config_filename,
        env.telemetry_webhook_url,
    )

    idea_text = json.dumps(idea, indent=2)
    config_text = _prepare_config_text(idea_filename=idea_filename, telemetry=telemetry_block)
    idea_b64 = _encode_multiline(idea_text)
    config_b64 = _encode_multiline(config_text)

    docker_cmd = _build_remote_script(
        env=env,
        idea_filename=idea_filename,
        idea_content_b64=idea_b64,
        config_filename=config_filename,
        config_content_b64=config_b64,
        run_id=run_id,
    )

    creator = RunPodCreator(api_key=runpod_api_key)
    github_key_b64 = base64.b64encode(env.git_deploy_key.encode()).decode()
    metadata_env = {
        "GIT_SSH_KEY_B64": github_key_b64,
        "REPO_NAME": "AE-Scientist",
        "REPO_ORG": "agencyenterprise",
        "REPO_BRANCH": "main",
        "OPENAI_API_KEY": env.openai_api_key,
        "HF_TOKEN": env.hf_token,
        "AWS_ACCESS_KEY_ID": env.aws_access_key_id,
        "AWS_SECRET_ACCESS_KEY": env.aws_secret_access_key,
        "AWS_REGION": env.aws_region,
        "AWS_S3_BUCKET_NAME": env.aws_s3_bucket_name,
        "RUN_ID": run_id,
        "DATABASE_PUBLIC_URL": env.database_public_url,
    }
    gpu_types = [
        "NVIDIA GeForce RTX 5090",
        "NVIDIA GeForce RTX 3090",
        "NVIDIA RTX A4000",
        "NVIDIA RTX A4500",
        "NVIDIA RTX A5000",
    ]
    pod_name = f"ae-scientist-{int(time.time())}"
    pod = creator.create_pod(
        name=pod_name,
        image="newtonsander/runpod_pytorch_texdeps:v1",
        gpu_types=gpu_types,
        env=metadata_env,
        docker_cmd=docker_cmd,
    )
    pod_id = pod["id"]
    ready_pod = creator.wait_for_pod_ready(pod_id=pod_id)
    pod_host_id = creator.get_pod_host_id(pod_id=pod_id)
    return {
        "pod_id": pod_id,
        "pod_name": pod.get("name"),
        "gpu_type": pod.get("gpu_type_requested"),
        "public_ip": ready_pod.get("publicIp"),
        "ssh_port": ready_pod.get("portMappings", {}).get("22"),
        "pod_host_id": pod_host_id,
    }


def terminate_pod(*, pod_id: str) -> None:
    runpod_api_key = os.environ.get("RUNPOD_API_KEY")
    if not runpod_api_key:
        raise RuntimeError("RUNPOD_API_KEY environment variable is required.")
    creator = RunPodCreator(api_key=runpod_api_key)
    try:
        creator.stop_pod(pod_id=pod_id)
    except RunPodError as exc:
        raise RuntimeError(f"Failed to terminate pod {pod_id}: {exc}") from exc
