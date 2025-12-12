"""
Launches the research pipeline on RunPod and injects refined ideas/configurations.
"""

import base64
import json
import logging
import os
import re
import shlex
import subprocess
import tempfile
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


class RunPodManager:
    def __init__(self, api_key: str):
        self.api_key = api_key
        base_url_override = os.environ.get("FAKE_RUNPOD_BASE_URL")
        graphql_url_override = os.environ.get("FAKE_RUNPOD_GRAPHQL_URL")
        self.base_url = base_url_override or "https://rest.runpod.io/v1"
        self.graphql_url = graphql_url_override or "https://api.runpod.io/graphql"
        self._session = requests.Session()

    def _make_request(
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

        response = requests.request(
            method=method,
            url=url,
            headers=headers,
            params=params,
            json=data,
            timeout=60,
        )
        if not response.ok:
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
        response = self._make_request(endpoint="/pods", method="POST", data=payload)
        if not isinstance(response, dict):
            raise RunPodError("Unexpected response while creating pod.", status=0)
        return response

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
        response = self._make_request(endpoint=f"/pods/{pod_id}")
        if not isinstance(response, dict):
            raise RunPodError("Unexpected response while retrieving pod.", status=0)
        return response

    def delete_pod(self, pod_id: str) -> None:
        self._make_request(endpoint=f"/pods/{pod_id}", method="DELETE", data=None)

    def get_pod_billing_summary(self, pod_id: str) -> dict[str, Any] | None:
        params = {"podId": pod_id, "grouping": "podId"}
        response = self._make_request(endpoint="/billing/pods", method="GET", params=params)
        if not isinstance(response, list):
            raise RunPodError("Unexpected billing response format.", status=0)
        logger.debug("Billing response: %s", response)
        if not response:
            logger.info("No billing records returned for pod %s; skipping summary.", pod_id)
            return None
        total_amount = 0.0
        total_ms = 0
        filtered_records: list[dict[str, Any]] = []
        for record in response:
            if record.get("podId") and record.get("podId") != pod_id:
                continue
            filtered_records.append(record)
            amount = record.get("amount")
            if amount is not None:
                try:
                    total_amount += float(amount)
                except (TypeError, ValueError):
                    logger.debug("Skipping invalid amount in billing record: %s", record)
            ms = record.get("timeBilledMs")
            if ms is not None:
                try:
                    total_ms += int(ms)
                except (TypeError, ValueError):
                    logger.debug("Skipping invalid timeBilledMs in billing record: %s", record)
        return {
            "pod_id": pod_id,
            "total_amount_usd": round(total_amount, 6),
            "time_billed_ms": total_ms,
            "record_count": len(filtered_records),
            "records": filtered_records,
        }

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

POD_NAME_PREFIX = "aeScientist"
_POD_USER_FALLBACK = "Scientist"
_POD_USER_MAX_LEN = 24


def _sanitize_pod_user_component(*, value: str) -> str:
    trimmed = value.strip()
    if not trimmed:
        return _POD_USER_FALLBACK
    sanitized = re.sub(pattern=r"[^A-Za-z0-9]", repl="", string=trimmed)
    if not sanitized:
        return _POD_USER_FALLBACK
    truncated = sanitized[:_POD_USER_MAX_LEN]
    return f"{truncated[0].upper()}{truncated[1:]}"


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
        "python - <<'PY' || { echo \"❌ PyTorch CUDA initialization failed\"; exit 1; }",
        "import torch",
        "torch.cuda.set_device(0)",
        "print('✅ PyTorch device initialized successfully')",
        "PY",
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
    requested_by_first_name: str,
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

    creator = RunPodManager(api_key=runpod_api_key)
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
    user_component = _sanitize_pod_user_component(value=requested_by_first_name)
    pod_name = f"{POD_NAME_PREFIX}-{user_component}-{int(time.time())}"
    pod = creator.create_pod(
        name=pod_name,
        image="newtonsander/runpod_pytorch_texdeps:v1",
        gpu_types=gpu_types,
        env=metadata_env,
        docker_cmd=docker_cmd,
    )
    logger.debug("Pod created: %s", pod)
    pod_id = pod["id"]
    ready_pod = creator.wait_for_pod_ready(pod_id=pod_id)
    pod_host_id = creator.get_pod_host_id(pod_id=pod_id)
    return {
        "pod_id": pod_id,
        "pod_name": pod.get("name"),
        "gpu_type": pod.get("gpu_type_requested"),
        "costPerHr": pod.get("costPerHr"),
        "public_ip": ready_pod.get("publicIp"),
        "ssh_port": ready_pod.get("portMappings", {}).get("22"),
        "pod_host_id": pod_host_id,
    }


def terminate_pod(*, pod_id: str) -> None:
    runpod_api_key = os.environ.get("RUNPOD_API_KEY")
    if not runpod_api_key:
        raise RuntimeError("RUNPOD_API_KEY environment variable is required.")
    creator = RunPodManager(api_key=runpod_api_key)
    try:
        creator.delete_pod(pod_id=pod_id)
    except RunPodError as exc:
        raise RuntimeError(f"Failed to terminate pod {pod_id}: {exc}") from exc


def fetch_pod_billing_summary(*, pod_id: str) -> dict[str, Any] | None:
    runpod_api_key = os.environ.get("RUNPOD_API_KEY")
    if not runpod_api_key:
        raise RuntimeError("RUNPOD_API_KEY environment variable is required.")
    manager = RunPodManager(api_key=runpod_api_key)
    return manager.get_pod_billing_summary(pod_id=pod_id)


_LOG_UPLOAD_REQUIRED_ENVS = [
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "AWS_REGION",
    "AWS_S3_BUCKET_NAME",
]


def _gather_log_env(run_id: str) -> dict[str, str] | None:
    env_values: dict[str, str] = {"RUN_ID": run_id}
    missing: list[str] = []
    for name in _LOG_UPLOAD_REQUIRED_ENVS:
        value = os.environ.get(name)
        if not value:
            missing.append(name)
        else:
            env_values[name] = value
    database_public = os.environ.get("DATABASE_PUBLIC_URL")
    if not database_public:
        missing.append("DATABASE_PUBLIC_URL")
    else:
        env_values["DATABASE_PUBLIC_URL"] = database_public
        env_values["DATABASE_URL"] = os.environ.get("DATABASE_URL", database_public)
    if missing:
        logger.info("Missing env vars for pod log upload: %s", ", ".join(sorted(set(missing))))
        return None
    return env_values


def _write_temp_key_file(raw_key: str) -> str:
    key_material = raw_key.replace("\\n", "\n").strip() + "\n"
    fd, path = tempfile.mkstemp(prefix="runpod-key-", suffix=".pem")
    with os.fdopen(fd, "w") as handle:
        handle.write(key_material)
    os.chmod(path, 0o600)
    return path


def upload_runpod_log_via_ssh(*, host: str, port: str | int, run_id: str) -> None:
    if not host or not port:
        logger.info("Skipping pod log upload for run %s; missing host/port.", run_id)
        return
    private_key = os.environ.get("RUN_POD_SSH_ACCESS_KEY")
    if not private_key:
        logger.info("RUN_POD_SSH_ACCESS_KEY is not configured; skipping pod log upload.")
        return
    env_values = _gather_log_env(run_id)
    if env_values is None:
        return
    key_path = _write_temp_key_file(private_key)
    remote_env = " ".join(f"{name}={shlex.quote(value)}" for name, value in env_values.items())
    remote_command = (
        "cd /workspace/AE-Scientist/research_pipeline && "
        "source .venv/bin/activate && "
        f"{remote_env} python upload_runpod_log.py "
        "--log-path /workspace/research_pipeline.log --artifact-type run_log"
    )
    ssh_command = [
        "ssh",
        "-i",
        key_path,
        "-o",
        "StrictHostKeyChecking=no",
        "-o",
        "UserKnownHostsFile=/dev/null",
        "-p",
        str(port),
        f"root@{host}",
        "bash",
        "-lc",
        shlex.quote(remote_command),
    ]
    try:
        result = subprocess.run(
            ssh_command,
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )
        if result.returncode != 0:
            logger.warning(
                "Pod log upload via SSH failed for run %s (exit %s): %s",
                run_id,
                result.returncode,
                result.stderr.strip(),
            )
        else:
            if result.stdout:
                logger.info(
                    "Pod log upload output for run %s: %s",
                    run_id,
                    result.stdout.strip(),
                )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Error uploading pod log for run %s: %s", run_id, exc)
    finally:
        try:
            Path(key_path).unlink(missing_ok=True)
        except OSError:
            pass
