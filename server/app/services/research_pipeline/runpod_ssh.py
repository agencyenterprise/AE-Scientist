"""
SSH helpers for communicating with the management webserver running inside the pod.
"""

import base64
import json
import logging
import os
import shlex
import subprocess
import tempfile
from pathlib import Path
from typing import Type

logger = logging.getLogger(__name__)


class TerminationRequestError(Exception):
    """Generic error when sending termination requests to the pipeline pod."""


class TerminationConflictError(TerminationRequestError):
    """Raised when the targeted execution already finished or is terminating."""


class TerminationNotFoundError(TerminationRequestError):
    """Raised when the targeted execution_id cannot be found on the pod."""


def _write_temp_key_file(raw_key: str) -> str:
    key_material = raw_key.replace("\\n", "\n").strip() + "\n"
    fd, path = tempfile.mkstemp(prefix="runpod-key-", suffix=".pem")
    with os.fdopen(fd, "w") as handle:
        handle.write(key_material)
    os.chmod(path, 0o600)
    return path


def _perform_management_ssh_request(
    *,
    host: str,
    port: str | int,
    payload: dict[str, object],
    endpoint: str,
    private_key: str,
    timeout: int,
    error_cls: Type[Exception],
) -> tuple[int, str]:
    payload_json = json.dumps(payload, ensure_ascii=False)
    payload_b64 = base64.b64encode(payload_json.encode("utf-8")).decode("utf-8")
    key_path = _write_temp_key_file(private_key)
    remote_command = (
        f"PAYLOAD=$(printf '%s' '{payload_b64}' | base64 --decode); "
        "RESPONSE=$(curl -sS -w '\\n%{http_code}' "
        "-H 'Content-Type: application/json' "
        '--data "$PAYLOAD" '
        f"http://127.0.0.1:8090{endpoint}); "
        "STATUS=$(printf '%s' \"$RESPONSE\" | tail -n1); "
        "BODY=$(printf '%s' \"$RESPONSE\" | sed '$d'); "
        "printf 'HTTP_STATUS:%s\\n' \"$STATUS\"; "
        "printf '%s' \"$BODY\""
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
            timeout=timeout,
            check=False,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("SSH management request failed (endpoint=%s)", endpoint)
        raise error_cls(f"SSH command failed for endpoint {endpoint}") from exc
    finally:
        try:
            Path(key_path).unlink(missing_ok=True)
        except OSError:
            pass

    stdout = result.stdout.strip() if result.stdout else ""
    stderr = result.stderr.strip() if result.stderr else ""
    if result.returncode != 0:
        raise error_cls(
            f"SSH command exited with {result.returncode} for endpoint {endpoint}: {stderr}"
        )

    status_line, _, body = stdout.partition("\n")
    if not status_line.startswith("HTTP_STATUS:"):
        raise error_cls(
            f"Malformed response from management server for endpoint {endpoint}: {stdout}"
        )
    status_code = status_line.split(":", 1)[1].strip()
    return int(status_code or "0"), body.strip()


def send_execution_feedback_via_ssh(
    *,
    host: str,
    port: str | int,
    execution_id: str,
    payload: str,
) -> None:
    """
    Kill a running execution inside the research pipeline pod and submit user feedback payload.

    This connects via SSH and sends a POST request to the local termination server running
    alongside the pipeline (default http://127.0.0.1:8090/terminate/{execution_id}).
    """
    if not host or not port:
        logger.warning("Cannot send feedback for execution %s; missing host or port.", execution_id)
        return
    private_key = os.environ.get("RUN_POD_SSH_ACCESS_KEY")
    if not private_key:
        logger.warning(
            "RUN_POD_SSH_ACCESS_KEY not configured; skipping feedback for execution %s",
            execution_id,
        )
        return

    status_code, body = _perform_management_ssh_request(
        host=host,
        port=port,
        payload={"payload": payload},
        endpoint=f"/terminate/{execution_id}",
        private_key=private_key,
        timeout=60,
        error_cls=TerminationRequestError,
    )

    if status_code == 200:
        logger.info(
            "Termination acknowledged for execution %s: %s", execution_id, body or "<empty>"
        )
        return

    if status_code == 404:
        raise TerminationNotFoundError(
            f"Execution {execution_id} not found on pod (response: {body or 'no body'})"
        )

    if status_code == 409:
        raise TerminationConflictError(
            f"Execution {execution_id} already completed or terminating (response: {body or 'no body'})"
        )

    raise TerminationRequestError(
        f"Unexpected termination response for execution {execution_id}: status={status_code} body={body}"
    )


def request_stage_skip_via_ssh(
    *,
    host: str,
    port: str | int,
    reason: str | None,
) -> None:
    """
    Request the pipeline to skip the current stage via the management server.
    """
    if not host or not port:
        raise RuntimeError("Cannot request stage skip; missing host or port.")
    private_key = os.environ.get("RUN_POD_SSH_ACCESS_KEY")
    if not private_key:
        raise RuntimeError("RUN_POD_SSH_ACCESS_KEY not configured; cannot request stage skip.")

    resolved_reason = reason or "Skip stage requested via dashboard."
    status_code, body = _perform_management_ssh_request(
        host=host,
        port=port,
        payload={"reason": resolved_reason},
        endpoint="/skip-stage",
        private_key=private_key,
        timeout=30,
        error_cls=RuntimeError,
    )

    if status_code != 200:
        raise RuntimeError(
            f"Stage skip request rejected: status={status_code} body={body or '<empty>'}"
        )

    logger.info("Stage skip request acknowledged by management server: %s", body or "<empty>")
