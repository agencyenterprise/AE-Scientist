import logging
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger("ai-scientist")


@dataclass(frozen=True)
class ScriptExecutionResult:
    term_out: list[str]
    exec_time_s: float
    exc_type: str | None
    exc_info: dict[str, object]


def run_python_script(
    *,
    purpose: str,
    python_executable: Path,
    script_path: Path,
    cwd: Path,
    env: dict[str, str],
    timeout_seconds: int,
) -> ScriptExecutionResult:
    started_at = time.time()
    try:
        proc = subprocess.run(
            args=[str(python_executable), str(script_path)],
            cwd=str(cwd),
            env=env,
            capture_output=True,
            text=True,
            timeout=float(timeout_seconds),
            check=False,
        )
    except subprocess.TimeoutExpired:
        exec_time_s = time.time() - started_at
        term_out = [f"Timed out running {script_path.name}\n"]
        logger.debug(
            "subprocess.python.timeout purpose=%s script=%s cwd=%s exec_time_s=%s timeout_s=%s term_out=%s",
            purpose,
            script_path,
            cwd,
            exec_time_s,
            timeout_seconds,
            term_out,
        )
        return ScriptExecutionResult(
            term_out=term_out,
            exec_time_s=exec_time_s,
            exc_type="ExecutionTimeout",
            exc_info={"reason": "timeout", "timeout_seconds": timeout_seconds},
        )
    except OSError as exc:
        exec_time_s = time.time() - started_at
        term_out = [f"Failed to execute {script_path.name}: {exc}\n"]
        logger.debug(
            "subprocess.python.os_error purpose=%s script=%s cwd=%s exec_time_s=%s error=%s term_out=%s",
            purpose,
            script_path,
            cwd,
            exec_time_s,
            str(exc),
            term_out,
        )
        return ScriptExecutionResult(
            term_out=term_out,
            exec_time_s=exec_time_s,
            exc_type="ExecutionRunnerError",
            exc_info={"reason": str(exc)},
        )

    exec_time_s = time.time() - started_at
    combined = (
        (proc.stdout or "") + ("\n" if proc.stdout and proc.stderr else "") + (proc.stderr or "")
    )
    term_out = [line + "\n" for line in combined.splitlines()]
    exc_type = None if proc.returncode == 0 else "ExecutionError"
    exc_info: dict[str, object] = {"returncode": proc.returncode}
    logger.debug(
        "subprocess.python.finished purpose=%s script=%s cwd=%s exec_time_s=%s returncode=%s exc_type=%s term_out=%s",
        purpose,
        script_path,
        cwd,
        exec_time_s,
        proc.returncode,
        exc_type,
        term_out,
    )
    return ScriptExecutionResult(
        term_out=term_out,
        exec_time_s=exec_time_s,
        exc_type=exc_type,
        exc_info=exc_info,
    )
