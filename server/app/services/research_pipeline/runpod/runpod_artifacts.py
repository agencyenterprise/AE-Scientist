"""
SSH helpers for uploading pod artifacts (logs, workspace archives) back to storage.
"""

import asyncio
import logging
import shlex
import subprocess
from pathlib import Path

from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_fixed

from app.config import settings

from .runpod_initialization import WORKSPACE_PATH
from .runpod_ssh import write_temp_key_file

logger = logging.getLogger(__name__)

ARTIFACT_UPLOAD_TIMEOUT_SECONDS = 180 * 60  # 3 hours


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_fixed(5),
    retry=retry_if_exception_type(subprocess.TimeoutExpired),
)
def _run_artifact_upload_command(
    *, command: list[str], timeout_seconds: int
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        check=False,
    )


async def upload_runpod_artifacts_via_ssh(
    *,
    host: str,
    port: str | int,
    run_id: str,
    trigger: str,
) -> None:
    await asyncio.to_thread(
        _upload_runpod_artifacts_via_ssh_sync,
        host=host,
        port=port,
        run_id=run_id,
        trigger=trigger,
    )


def _upload_runpod_artifacts_via_ssh_sync(
    *,
    host: str,
    port: str | int,
    run_id: str,
    trigger: str,
) -> None:
    if not host or not port:
        logger.info(
            "Skipping pod artifacts upload for run %s (trigger=%s); missing host/port.",
            run_id,
            trigger,
        )
        return
    logger.info(
        "Starting pod artifacts upload via SSH (run=%s trigger=%s host=%s port=%s)",
        run_id,
        trigger,
        host,
        port,
    )
    key_path = write_temp_key_file(settings.runpod_ssh_access_key)
    # Source the pod's .env file which contains TELEMETRY_WEBHOOK_URL, TELEMETRY_WEBHOOK_TOKEN, and RUN_ID
    env_file = f"{WORKSPACE_PATH}/AE-Scientist/research_pipeline/.env"
    log_file = f"{WORKSPACE_PATH}/research_pipeline.log"
    upload_log_file = f"{WORKSPACE_PATH}/upload_log.txt"
    # Wrap upload commands in a subshell with tee to log to upload_log.txt
    # Use -u for unbuffered Python output and stdbuf for unbuffered tee
    remote_command = (
        f"cd {WORKSPACE_PATH}/AE-Scientist/research_pipeline && "
        f"set -a && source {env_file} && set +a && "
        "( "
        # Upload the run log
        "echo '=== Uploading run log ===' && "
        f".venv/bin/python -u upload_file.py "
        f"--file-path {log_file} --artifact-type run_log 2>&1 || true; "
        # Upload the workspace archive
        "echo '=== Uploading workspace archive ===' && "
        ".venv/bin/python -u upload_folder.py "
        f"--folder-path {WORKSPACE_PATH}/AE-Scientist/research_pipeline/workspaces "
        "--artifact-type workspace_archive "
        "--archive-name workspace.zip 2>&1"
        f" ) 2>&1 | tee -a {upload_log_file}"
    )
    ssh_command = [
        "ssh",
        "-i",
        key_path,
        "-o",
        "StrictHostKeyChecking=no",
        "-o",
        "UserKnownHostsFile=/dev/null",
        "-o",
        "ServerAliveInterval=30",
        "-o",
        "ServerAliveCountMax=6",
        "-p",
        str(port),
        f"root@{host}",
        "bash",
        "-lc",
        shlex.quote(remote_command),
    ]
    try:
        result = _run_artifact_upload_command(
            command=ssh_command,
            timeout_seconds=ARTIFACT_UPLOAD_TIMEOUT_SECONDS,
        )
        # Log combined output (stdout + stderr) for visibility
        combined_output = (result.stdout or "") + (result.stderr or "")
        if combined_output.strip():
            log_level = logging.WARNING if result.returncode != 0 else logging.INFO
            logger.log(
                log_level,
                "Pod artifacts upload for run %s (trigger=%s, exit=%s):\n%s",
                run_id,
                trigger,
                result.returncode,
                combined_output.strip(),
            )
    except Exception as exc:  # noqa: BLE001  # pylint: disable=broad-exception-caught
        logger.exception(
            "Error uploading pod artifacts for run %s (trigger=%s): %s", run_id, trigger, exc
        )
    finally:
        try:
            Path(key_path).unlink(missing_ok=True)
        except OSError:
            pass
