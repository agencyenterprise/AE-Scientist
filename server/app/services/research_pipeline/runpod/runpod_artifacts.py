"""
SSH helpers for uploading pod artifacts (logs, workspace archives) back to storage.
"""

import asyncio
import logging
import os
import shlex
import subprocess
from pathlib import Path

from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_fixed

from .runpod_ssh import write_temp_key_file

logger = logging.getLogger(__name__)

ARTIFACT_UPLOAD_TIMEOUT_SECONDS = 40 * 60

_LOG_UPLOAD_REQUIRED_ENVS = [
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "AWS_REGION",
    "AWS_S3_BUCKET_NAME",
]


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
    private_key = os.environ.get("RUN_POD_SSH_ACCESS_KEY")
    if not private_key:
        logger.info(
            "Skipping pod artifacts upload for run %s (trigger=%s); RUN_POD_SSH_ACCESS_KEY is not configured.",
            run_id,
            trigger,
        )
        return
    env_values = _gather_log_env(run_id)
    if env_values is None:
        return
    logger.info(
        "Starting pod artifacts upload via SSH (run=%s trigger=%s host=%s port=%s)",
        run_id,
        trigger,
        host,
        port,
    )
    key_path = write_temp_key_file(private_key)
    remote_env = " ".join(f"{name}={shlex.quote(value)}" for name, value in env_values.items())
    remote_command = (
        "cd /workspace/AE-Scientist/research_pipeline && "
        f"{remote_env} .venv/bin/python upload_file.py "
        "--file-path /workspace/research_pipeline.log --artifact-type run_log || true && "
        f"{remote_env} .venv/bin/python upload_folder.py "
        "--folder-path /workspace/AE-Scientist/research_pipeline/workspaces/0-run "
        "--artifact-type workspace_archive "
        "--archive-name 0-run-workspace.zip"
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
        result = _run_artifact_upload_command(
            command=ssh_command,
            timeout_seconds=ARTIFACT_UPLOAD_TIMEOUT_SECONDS,
        )
        if result.returncode != 0:
            logger.warning(
                "Pod artifacts upload via SSH failed for run %s (trigger=%s, exit %s): %s",
                run_id,
                trigger,
                result.returncode,
                (result.stderr or "").strip(),
            )
        else:
            if result.stdout:
                logger.info(
                    "Pod artifacts upload output for run %s (trigger=%s): %s",
                    run_id,
                    trigger,
                    result.stdout.strip(),
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
