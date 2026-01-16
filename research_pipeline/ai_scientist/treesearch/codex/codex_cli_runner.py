import json
import logging
import os
import selectors
import subprocess
import time
from pathlib import Path
from typing import IO, Callable, cast

from ...llm.token_tracker import save_cost_track
from ..events import BaseEvent, RunLogEvent
from ..process_utils import terminate_process_group

logger = logging.getLogger("ai-scientist")


def _managed_venv_dir(*, workspace_dir: Path) -> Path:
    return workspace_dir / ".ai_scientist_venv"


def _venv_python_path(*, venv_dir: Path) -> Path:
    python_path = venv_dir / "bin" / "python"
    if python_path.exists():
        return python_path
    raise FileNotFoundError(f"Python executable not found in venv at {venv_dir}")


def _run_uv(
    *, args: list[str], timeout_seconds: int, extra_env: dict[str, str], cwd: Path
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    for key, value in extra_env.items():
        env[key] = value
    return subprocess.run(
        args=["uv", *args],
        check=True,
        capture_output=True,
        text=True,
        timeout=float(timeout_seconds),
        env=env,
        cwd=str(cwd),
    )


def ensure_codex_venv(*, workspace_dir: Path, research_pipeline_root: Path) -> Path:
    """
    Ensure a per-workspace venv exists (under the worker's workspace dir) and has project deps.

    This venv is used by Codex so `python` / `pip` resolve consistently during the run.
    """
    venv_dir = _managed_venv_dir(workspace_dir=workspace_dir)
    if not venv_dir.exists():
        _run_uv(
            args=["venv", "--system-site-packages", str(venv_dir)],
            timeout_seconds=600,
            extra_env={},
            cwd=workspace_dir,
        )
    venv_python = _venv_python_path(venv_dir=venv_dir)

    src_pyproject = research_pipeline_root / "pyproject.toml"
    dst_pyproject = workspace_dir / "pyproject.toml"
    if src_pyproject.exists():
        dst_pyproject.write_text(src_pyproject.read_text(encoding="utf-8"), encoding="utf-8")

    src_lock = research_pipeline_root / "uv.lock"
    dst_lock = workspace_dir / "uv.lock"
    if src_lock.exists():
        dst_lock.write_text(src_lock.read_text(encoding="utf-8"), encoding="utf-8")

    _run_uv(
        args=["sync"],
        timeout_seconds=600,
        extra_env={
            "UV_PROJECT_ENVIRONMENT": str(venv_dir),
            "UV_PYTHON": str(venv_python),
        },
        cwd=workspace_dir,
    )
    return venv_dir


def build_codex_exec_env(*, base_env: dict[str, str]) -> dict[str, str]:
    env = dict(base_env)
    openai_api_key = env.get("OPENAI_API_KEY")
    if openai_api_key:
        env["CODEX_API_KEY"] = openai_api_key
    env["CI"] = "1"
    env["NO_UPDATE_NOTIFIER"] = "1"
    env["DISABLE_UPDATE_NOTIFIER"] = "1"
    env["npm_config_update_notifier"] = "false"
    return env


def build_codex_env(*, venv_dir: Path) -> dict[str, str]:
    env = os.environ.copy()
    bin_dir = venv_dir / "bin"
    env["VIRTUAL_ENV"] = str(venv_dir)
    env["PATH"] = f"{bin_dir}{os.pathsep}{env.get('PATH', '')}"
    env["PIP_REQUIRE_VIRTUALENV"] = "1"
    env["PYTHONNOUSERSITE"] = "1"
    return build_codex_exec_env(base_env=env)


class CodexCliRunner:
    def __init__(
        self,
        *,
        workspace_dir: Path,
        session_log_name: str,
        events_log_name: str,
        timeout_seconds: int,
        model: str,
        env: dict[str, str],
        event_callback: Callable[[BaseEvent], None],
    ) -> None:
        self._workspace_dir = workspace_dir
        self._session_log_name = session_log_name
        self._events_log_name = events_log_name
        self._timeout_seconds = timeout_seconds
        self._model = model
        self._env = dict(env)
        self._event_callback = event_callback

    def run(
        self,
        *,
        task_file: Path,
        pid_callback: Callable[[int], None] | None,
        termination_checker: Callable[[], bool] | None,
    ) -> tuple[list[str], float, str | None, dict[str, object] | None]:
        """
        Run Codex CLI inside workspace_dir using a task file.

        This runner assumes Codex is invoked in a non-interactive mode. If Codex blocks
        waiting for user input, it will consume the wall-clock timeout and be killed.
        """
        started_at = time.monotonic()
        log_path = self._workspace_dir / self._session_log_name
        events_path = self._workspace_dir / self._events_log_name
        log_path.parent.mkdir(parents=True, exist_ok=True)

        # Use non-interactive automation mode via `codex exec`.
        # See docs: https://developers.openai.com/codex/noninteractive
        prompt = task_file.read_text(encoding="utf-8", errors="replace")
        argv = [
            "codex",
            "exec",
            "--yolo",
            "--skip-git-repo-check",
            "--json",
            "--model",
            self._model,
            prompt,
        ]
        logger.info("Starting Codex CLI: %s (cwd=%s)", " ".join(argv), self._workspace_dir)

        proc: subprocess.Popen[bytes] | None = None
        try:
            with (
                open(log_path, "ab") as logf,
                open(events_path, "ab") as eventsf,
            ):
                proc = subprocess.Popen(
                    args=argv,
                    cwd=str(self._workspace_dir),
                    env=self._env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    start_new_session=True,
                    bufsize=0,
                )
                if pid_callback is not None:
                    pid_callback(proc.pid)

                assert proc.stdout is not None
                assert proc.stderr is not None
                stdout_pipe = proc.stdout
                stderr_pipe = proc.stderr

                sel = selectors.DefaultSelector()
                sel.register(stdout_pipe, selectors.EVENT_READ, data="stdout")
                sel.register(stderr_pipe, selectors.EVENT_READ, data="stderr")
                stdout_buf = b""

                def _maybe_emit_jsonl(line: str) -> None:
                    # Emit only high-signal items to the outer UI.
                    # Users can always inspect codex_events.jsonl for full detail.
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError:
                        return
                    if not isinstance(obj, dict):
                        return
                    typ = obj.get("type")
                    if typ == "error":
                        self._event_callback(
                            RunLogEvent(message=f"[codex:error] {line}", level="info")
                        )
                        return
                    if typ == "turn.completed":
                        self._event_callback(
                            RunLogEvent(message=f"[codex:{typ}] {line}", level="info")
                        )
                        # Extract and save token usage for cost tracking
                        usage = obj.get("usage")
                        if isinstance(usage, dict):
                            input_tokens = usage.get("input_tokens")
                            output_tokens = usage.get("output_tokens")
                            if input_tokens is not None and output_tokens is not None:
                                try:
                                    save_cost_track(
                                        self._model,
                                        input_tokens=int(input_tokens),
                                        output_tokens=int(output_tokens),
                                    )
                                except Exception:
                                    logger.exception("Failed to save token usage")
                        return
                    if typ in ("thread.started", "turn.started", "turn.failed"):
                        self._event_callback(
                            RunLogEvent(message=f"[codex:{typ}] {line}", level="info")
                        )
                        return
                    if typ == "item.started":
                        self._event_callback(
                            RunLogEvent(message=f"[codex:{typ}] {line}", level="info")
                        )
                        return
                    item = obj.get("item")
                    if not isinstance(item, dict):
                        return
                    item_type = item.get("type")
                    if item_type == "agent_message":
                        text = item.get("text")
                        if isinstance(text, str):
                            self._event_callback(
                                RunLogEvent(message=f"[codex:agent_message] {text}", level="info")
                            )
                        return
                    if item_type == "command_execution":
                        cmd = item.get("command")
                        status = item.get("status")
                        if isinstance(cmd, str):
                            cmd_one_line = " ".join(cmd.splitlines())
                            self._event_callback(
                                RunLogEvent(
                                    message=f"[codex:cmd:{status}] {cmd_one_line[:400]}",
                                    level="info",
                                )
                            )
                        return

                while True:
                    if termination_checker is not None and termination_checker():
                        logger.info("Codex run terminated by external request (pid=%s)", proc.pid)
                        terminate_process_group(pid=proc.pid, grace_seconds=1.0)
                        return self._build_result_from_log(
                            events_path=events_path,
                            started_at=started_at,
                            exc_type="Terminated",
                            exc_info={"reason": "terminated"},
                        )

                    # Drain any available output without blocking indefinitely.
                    for key, _ in sel.select(timeout=0.1):
                        stream = cast(IO[bytes], key.fileobj)
                        chunk = stream.read(4096)
                        if not chunk:
                            continue
                        logf.write(chunk)
                        logf.flush()
                        if key.data == "stderr":
                            # Codex progress lines are typically on stderr (human readable).
                            try:
                                decoded_chunk = chunk.decode("utf-8", errors="replace").rstrip()
                                self._event_callback(
                                    RunLogEvent(
                                        message=f"[codex:stderr] {decoded_chunk}", level="info"
                                    )
                                )
                            except (ValueError, TypeError):
                                pass
                            continue

                        # With `codex exec --json`, stdout is JSONL.
                        stdout_buf += chunk
                        while b"\n" in stdout_buf:
                            raw_line, stdout_buf = stdout_buf.split(b"\n", 1)
                            json_line = raw_line + b"\n"
                            eventsf.write(json_line)
                            eventsf.flush()
                            line_str = json_line.decode("utf-8", errors="replace").rstrip("\n")
                            _maybe_emit_jsonl(line_str)

                    rc = proc.poll()
                    if rc is not None:
                        break

                    elapsed = time.monotonic() - started_at
                    if elapsed > float(self._timeout_seconds):
                        logger.info(
                            "Codex run timed out after %ss (pid=%s)",
                            self._timeout_seconds,
                            proc.pid,
                        )
                        terminate_process_group(pid=proc.pid, grace_seconds=1.0)
                        return self._build_result_from_log(
                            events_path=events_path,
                            started_at=started_at,
                            exc_type="TimeoutError",
                            exc_info={
                                "reason": "timeout",
                                "timeout_seconds": self._timeout_seconds,
                            },
                        )
        except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
            if proc is not None and proc.poll() is None:
                terminate_process_group(pid=proc.pid, grace_seconds=1.0)
            logger.warning("Codex CLI run crashed: %s", exc, exc_info=True)
            return self._build_result_from_log(
                events_path=events_path,
                started_at=started_at,
                exc_type="CodexRunnerError",
                exc_info={"reason": str(exc)},
            )

        assert proc is not None
        returncode = proc.returncode
        if returncode == 0:
            return self._build_result_from_log(
                events_path=events_path,
                started_at=started_at,
                exc_type=None,
                exc_info={"returncode": returncode},
            )
        return self._build_result_from_log(
            events_path=events_path,
            started_at=started_at,
            exc_type="CodexError",
            exc_info={"returncode": returncode},
        )

    def _build_result_from_log(
        self,
        *,
        events_path: Path,
        started_at: float,
        exc_type: str | None,
        exc_info: dict[str, object] | None,
    ) -> tuple[list[str], float, str | None, dict[str, object] | None]:
        exec_time = time.monotonic() - started_at
        term_out: list[str] = []
        try:
            if events_path.exists():
                text = events_path.read_text(encoding="utf-8", errors="replace")
                # `events_path` is JSONL; keep line-based segments (list[str]) for downstream.
                term_out = [line + "\n" for line in text.splitlines()]
        except OSError:
            logger.debug("Failed reading Codex events at %s", events_path, exc_info=True)
        return term_out, exec_time, exc_type, exc_info
