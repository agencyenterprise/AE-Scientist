"""
Builds the initialization scripts and configuration injected into a freshly launched RunPod pod.
"""

import base64
import logging
import os
import re
import shlex
from dataclasses import dataclass
from pathlib import Path

from omegaconf import OmegaConf

logger = logging.getLogger(__name__)

CONFIG_TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "bfts_config_template.yaml"
RUNPOD_SETUP_SCRIPT_PATH = Path(__file__).resolve().parent / "runpod_repo_setup.sh"

CONTAINER_DISK_GB = 100
WORKSPACE_DISK_GB = 200
_POD_NAME_PREFIX = "aescientist"
_POD_USER_FALLBACK = "Scientist"
_POD_USER_MAX_LEN = 24

WORKSPACE_PATH = "/workspace"
DEFAULT_COLLECT_DISK_STATS_PATHS = f"/,{WORKSPACE_PATH}"
DISK_STATS_ENV_NAME = "COLLECT_DISK_STATS_PATHS"


def _sanitize_pod_user_component(*, value: str) -> str:
    trimmed = value.strip()
    if not trimmed:
        return _POD_USER_FALLBACK
    sanitized = re.sub(pattern=r"[^A-Za-z0-9]", repl="", string=trimmed)
    if not sanitized:
        return _POD_USER_FALLBACK
    truncated = sanitized[:_POD_USER_MAX_LEN]
    return truncated.lower()


def get_pod_name(*, user_name: str, run_id: str) -> str:
    return f"{_POD_NAME_PREFIX}_{_sanitize_pod_user_component(value=user_name)}_{run_id}"


@dataclass
class RunPodEnvironment:
    git_deploy_key: str
    openai_api_key: str
    hf_token: str
    telemetry_webhook_url: str
    sentry_dsn: str
    sentry_environment: str


def load_runpod_environment() -> RunPodEnvironment:
    def _require(name: str) -> str:
        value = os.environ.get(name)
        if not value:
            raise RuntimeError(f"Environment variable {name} is required to launch RunPod.")
        return value

    def _optional(name: str) -> str:
        value = os.environ.get(name)
        return value or ""

    return RunPodEnvironment(
        git_deploy_key=_require("GIT_DEPLOY_KEY").replace("\\n", "\n"),
        openai_api_key=_require("OPENAI_API_KEY"),
        hf_token=_require("HF_TOKEN"),
        telemetry_webhook_url=_require("TELEMETRY_WEBHOOK_URL"),
        sentry_dsn=_optional("SENTRY_DSN"),
        sentry_environment=_optional("SENTRY_ENVIRONMENT") or _optional("RAILWAY_ENVIRONMENT_NAME"),
    )


def prepare_config_text(*, title: str, idea_filename: str, telemetry: dict[str, str]) -> str:
    if not CONFIG_TEMPLATE_PATH.exists():
        raise RuntimeError(
            "Pipeline config template missing at "
            f"{CONFIG_TEMPLATE_PATH}. Ensure the file exists."
        )
    config = OmegaConf.load(CONFIG_TEMPLATE_PATH)
    logger.debug(
        "Preparing pipeline config from %s with title=%s, desc_file=%s",
        CONFIG_TEMPLATE_PATH,
        title,
        idea_filename,
    )
    config.title = title
    config.desc_file = idea_filename
    if telemetry:
        config.telemetry = telemetry
    else:
        config.telemetry = None
    config_yaml = OmegaConf.to_yaml(config)
    if not config_yaml.endswith("\n"):
        config_yaml += "\n"
    return config_yaml


def encode_multiline(value: str) -> str:
    return base64.b64encode(value.encode("utf-8")).decode("utf-8")


def _repository_setup_commands() -> list[str]:
    if not RUNPOD_SETUP_SCRIPT_PATH.exists():
        raise RuntimeError(
            f"RunPod setup script missing at {RUNPOD_SETUP_SCRIPT_PATH}. "
            "Ensure server/app/services/research_pipeline/runpod/runpod_repo_setup.sh exists."
        )
    script_text = RUNPOD_SETUP_SCRIPT_PATH.read_text(encoding="utf-8").strip()
    return [
        "# === Repository Setup ===",
        "cat <<'RUNPOD_SETUP' | bash",
        script_text,
        "RUNPOD_SETUP",
        "",
    ]


def _python_packages_installation_commands() -> list[str]:
    return [
        "# === Installation ===",
        'echo "Running installation script..."',
        f"cd {WORKSPACE_PATH}/AE-Scientist",
        "cat <<'RUNPOD_INSTALL' | bash",
        f"cd {WORKSPACE_PATH}/AE-Scientist/research_pipeline/",
        "uv venv --system-site-packages",
        "source .venv/bin/activate",
        "uv sync",
        "RUNPOD_INSTALL",
        "",
    ]


def _codex_installation_commands() -> list[str]:
    return [
        "# === Codex CLI Installation ===",
        'echo "Ensuring Codex CLI is installed..."',
        "if ! command -v codex >/dev/null 2>&1; then",
        "  if ! command -v npm >/dev/null 2>&1; then",
        '    echo "npm not found; installing Node.js + npm..."',
        "    apt-get update && apt-get install -y nodejs npm",
        "  fi",
        "  npm install -g @openai/codex",
        "fi",
        "codex --version || true",
        "",
    ]


def _download_parent_run_data_commands() -> list[str]:
    return [
        "# === Download Parent Run Data ===",
        'if [ "${HAS_PREVIOUS_RUN:-false}" = "true" ] && [ -n "${PARENT_RUN_ID:-}" ]; then',
        '  echo "Downloading parent run data from ${PARENT_RUN_ID}..."',
        '  mkdir -p "${PREVIOUS_RUN_DATA_PATH}"',
        f'  python download_parent_run.py --parent-run-id "${{PARENT_RUN_ID}}" --output "${{PREVIOUS_RUN_DATA_PATH}}" >{WORKSPACE_PATH}/parent_run_download.log 2>&1 &',
        '  echo "Started parent run data download in background (pid=$!)"',
        "else",
        '  echo "No parent run data to download"',
        "fi",
        "",
    ]


def _inject_refined_idea_and_config_commands(
    *,
    idea_filename: str,
    idea_content_b64: str,
    config_filename: str,
    config_content_b64: str,
) -> list[str]:
    return [
        "# === Inject refined idea and config ===",
        f"cd {WORKSPACE_PATH}/AE-Scientist/research_pipeline",
        "python - <<'PY'",
        "import base64, pathlib",
        f"pathlib.Path('{idea_filename}').write_bytes(base64.b64decode('{idea_content_b64}'))",
        f"pathlib.Path('{config_filename}').write_bytes(base64.b64decode('{config_content_b64}'))",
        "PY",
        "",
    ]


def _pytorch_cuda_test_command() -> list[str]:
    return [
        'send_init_status "Initializing PyTorch"',
        "python - <<'PY' || { echo \"❌ PyTorch CUDA initialization failed\"; exit 1; }",
        "import torch",
        "torch.cuda.set_device(0)",
        "print('✅ PyTorch device initialized successfully')",
        "PY",
        "",
    ]


def _upload_scrubbed_run_config_commands(*, config_filename: str) -> list[str]:
    return [
        "scrubbed_config_path=/tmp/run_config.yaml",
        f"yq eval 'del(.telemetry.database_url, .telemetry.webhook_token)' '{WORKSPACE_PATH}/AE-Scientist/research_pipeline/{config_filename}' > \"$scrubbed_config_path\"",
        'if [ -s "$scrubbed_config_path" ]; then',
        f'  python upload_file.py --file-path "$scrubbed_config_path" --artifact-type run_config >{WORKSPACE_PATH}/run_config_upload.log 2>&1 &',
        '  echo "Started run_config upload (pid=$!)"',
        "else",
        "  echo 'Sanitized config is empty; skipping upload.'",
        "fi",
    ]


def _launch_research_pipeline_commands(*, config_filename: str) -> list[str]:
    return [
        "pipeline_exit_code=0",
        "set +e",
        "# === Starting Research Pipeline ===",
        'echo "Launching research pipeline..."',
        'send_init_status "Launching research pipeline"',
        f"python -u launch_scientist_bfts.py '{config_filename}' 2>&1 | tee -a {WORKSPACE_PATH}/research_pipeline.log",
        "pipeline_exit_code=$?",
        "set -e",
        'if [ "$pipeline_exit_code" -eq 0 ]; then',
        f'  echo "Research pipeline completed successfully. Check {WORKSPACE_PATH}/research_pipeline.log for full output."',
        "else",
        f'  echo "Research pipeline failed. Check {WORKSPACE_PATH}/research_pipeline.log for details."',
        "fi",
        "",
    ]


def _await_external_cleanup_commands() -> list[str]:
    return [
        "# === Await External Cleanup ===",
        'echo "Research pipeline finished; sleeping until server collects artifacts..."',
        "while true; do sleep 3600; done",
    ]


def _resolve_disk_stats_paths() -> str:
    raw = os.environ.get(DISK_STATS_ENV_NAME) or DEFAULT_COLLECT_DISK_STATS_PATHS
    paths = [segment.strip() for segment in raw.split(",") if segment.strip()]
    sanitized = ",".join(paths) if paths else DEFAULT_COLLECT_DISK_STATS_PATHS
    return sanitized


def build_remote_script(
    *,
    env: RunPodEnvironment,
    idea_filename: str,
    idea_content_b64: str,
    config_filename: str,
    config_content_b64: str,
    run_id: str,
    has_previous_run: bool,
    webhook_token: str,
) -> str:
    telemetry_url = shlex.quote(env.telemetry_webhook_url.strip())
    telemetry_token = shlex.quote(webhook_token)
    run_id_quoted = shlex.quote(run_id)
    script_parts: list[str] = [
        "set -euo pipefail",
        "",
        f"export RUN_ID={run_id_quoted}",
        f"export TELEMETRY_WEBHOOK_URL={telemetry_url}",
        f"export TELEMETRY_WEBHOOK_TOKEN={telemetry_token}",
        "",
        "send_init_status() {",
        '  if [ -z "${TELEMETRY_WEBHOOK_URL:-}" ] || [ -z "${TELEMETRY_WEBHOOK_TOKEN:-}" ] || [ -z "${RUN_ID:-}" ]; then',
        "    return 0",
        "  fi",
        "  if ! command -v curl >/dev/null 2>&1; then",
        "    return 0",
        "  fi",
        '  msg="$1"',
        '  msg="${msg//\\"/\\\\\\"}"',
        '  payload="{\\"message\\":\\"${msg}\\"}"',
        '  curl -sS -X POST "${TELEMETRY_WEBHOOK_URL%/}/${RUN_ID}/initialization-progress" \\',
        '    -H "Authorization: Bearer ${TELEMETRY_WEBHOOK_TOKEN}" \\',
        '    -H "Content-Type: application/json" \\',
        '    --data "${payload}" >/dev/null 2>&1 || true',
        "}",
        "",
    ]
    hw_stats_paths = _resolve_disk_stats_paths()
    env_file_lines = [
        f"OPENAI_API_KEY={env.openai_api_key}",
        f"HF_TOKEN={env.hf_token}",
        f"TELEMETRY_WEBHOOK_URL={env.telemetry_webhook_url}",
        f"TELEMETRY_WEBHOOK_TOKEN={webhook_token}",
        f"RUN_ID={run_id}",
        f"{DISK_STATS_ENV_NAME}={hw_stats_paths}",
        f"PIPELINE_WORKSPACE_DISK_CAPACITY_BYTES={WORKSPACE_DISK_GB * 1024**3}",
        f"PIPELINE_WORKSPACE_PATH={WORKSPACE_PATH}",
        # Dataset configuration (not AWS credentials, just paths/folder names)
        f"DATASETS_LOCAL_DIR={WORKSPACE_PATH}/datasets",
        "DATASETS_AWS_FOLDER=datasets",
    ]
    if has_previous_run:
        env_file_lines.append('HAS_PREVIOUS_RUN="true"')
        env_file_lines.append(f"PREVIOUS_RUN_DATA_PATH={WORKSPACE_PATH}/previous_run_data")
    if env.sentry_dsn:
        env_file_lines.append(f"SENTRY_DSN={env.sentry_dsn}")
    if env.sentry_environment:
        env_file_lines.append(f"SENTRY_ENVIRONMENT={env.sentry_environment}")
    script_parts += [
        "# === GPU Validation ===",
        'send_init_status "Validating GPU"',
        'echo "Validating GPU..."',
        'nvidia-smi || { echo "❌ nvidia-smi failed"; exit 1; }',
        'echo "✅ GPU validated"',
        "",
    ]
    script_parts += ['send_init_status "Cloning repository"', ""]
    script_parts += _repository_setup_commands()
    script_parts += ['send_init_status "Installing packages"', ""]
    script_parts += _python_packages_installation_commands()
    script_parts += ['send_init_status "Installing Codex CLI"', ""]
    script_parts += _codex_installation_commands()
    script_parts += [
        "# === Environment Setup ===",
        'echo "Creating .env file..."',
        f"cd {WORKSPACE_PATH}/AE-Scientist/research_pipeline",
        "cat > .env << 'EOF'",
    ]
    script_parts += env_file_lines
    script_parts += [
        "EOF",
        'echo "Exporting environment variables from .env..."',
        "set -a",
        "source .env",
        "set +a",
        "",
    ]
    script_parts += _inject_refined_idea_and_config_commands(
        idea_filename=idea_filename,
        idea_content_b64=idea_content_b64,
        config_filename=config_filename,
        config_content_b64=config_content_b64,
    )
    script_parts += ["source .venv/bin/activate", ""]
    script_parts += _pytorch_cuda_test_command()
    script_parts += _download_parent_run_data_commands()
    script_parts += _upload_scrubbed_run_config_commands(config_filename=config_filename)
    script_parts += _launch_research_pipeline_commands(config_filename=config_filename)
    script_parts += _await_external_cleanup_commands()
    return "\n".join(script_parts).strip()
