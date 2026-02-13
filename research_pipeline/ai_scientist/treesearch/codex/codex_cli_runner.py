import json
import logging
import os
import selectors
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import IO, Callable, cast

from ...llm.token_tracker import save_cost_track
from ..events import BaseEvent, CodexEvent
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
    try:
        return subprocess.run(
            args=["uv", *args],
            check=True,
            capture_output=True,
            text=True,
            timeout=float(timeout_seconds),
            env=env,
            cwd=str(cwd),
        )
    except subprocess.CalledProcessError as e:
        logger.error(
            "uv command failed: %s (exit code %s)\nstdout: %s\nstderr: %s",
            e.cmd,
            e.returncode,
            e.stdout,
            e.stderr,
        )
        raise


def _setup_codex_venv(*, workspace_dir: Path, research_pipeline_root: Path, venv_dir: Path) -> Path:
    """
    Create venv and sync dependencies. Internal helper for ensure_codex_venv.
    """
    if not venv_dir.exists():
        _run_uv(
            args=["venv", "--system-site-packages", str(venv_dir)],
            timeout_seconds=1800,
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


def ensure_codex_venv(*, workspace_dir: Path, research_pipeline_root: Path) -> Path:
    """
    Ensure a per-workspace venv exists (under the worker's workspace dir) and has project deps.

    This venv is used by Codex so `python` / `pip` resolve consistently during the run.

    Includes retry logic to handle transient file system errors (e.g., stale NFS handles).
    """
    venv_dir = _managed_venv_dir(workspace_dir=workspace_dir)
    max_retries = 2

    for attempt in range(max_retries + 1):
        try:
            return _setup_codex_venv(
                workspace_dir=workspace_dir,
                research_pipeline_root=research_pipeline_root,
                venv_dir=venv_dir,
            )
        except subprocess.CalledProcessError:
            if attempt < max_retries:
                logger.warning(
                    "Venv setup failed (attempt %d/%d), removing venv and retrying: %s",
                    attempt + 1,
                    max_retries + 1,
                    venv_dir,
                )
                if venv_dir.exists():
                    shutil.rmtree(venv_dir, ignore_errors=True)
            else:
                raise

    raise RuntimeError("ensure_codex_venv: unreachable")


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
        research_pipeline_root: Path,
        session_log_name: str,
        events_log_name: str,
        timeout_seconds: int,
        model: str,
        event_callback: Callable[[BaseEvent], None],
        venv_dir: Path | None = None,
        env: dict[str, str] | None = None,
    ) -> None:
        self._workspace_dir = workspace_dir
        self._session_log_name = session_log_name
        self._events_log_name = events_log_name
        self._timeout_seconds = timeout_seconds
        self._model = model
        self._event_callback = event_callback

        # Auto-setup venv and environment if not provided
        if venv_dir is None:
            self._venv_dir = ensure_codex_venv(
                workspace_dir=workspace_dir,
                research_pipeline_root=research_pipeline_root,
            )
        else:
            self._venv_dir = venv_dir

        if env is None:
            self._env = build_codex_env(venv_dir=self._venv_dir)
        else:
            self._env = dict(env)

    def _build_argv(self) -> list[str]:
        """Build codex CLI command arguments."""
        # Codex CLI expects just the model name, not the provider:model format.
        # Extract just the model name (e.g., "gpt-5.2" from "openai:gpt-5.2")
        model_name = self._model.split(":", 1)[1] if ":" in self._model else self._model
        return [
            "codex",
            "exec",
            "--yolo",
            "--skip-git-repo-check",
            "--json",
            "--model",
            model_name,
            # Provide the prompt via stdin to avoid OS argv limits (E2BIG).
            # Codex treats "-" as "read instructions from stdin".
            "-",
        ]

    def _save_token_usage_from_jsonl(self, line: str) -> None:
        """Extract and save token usage from Codex JSONL event for cost tracking."""
        try:
            obj = json.loads(line)
            if not isinstance(obj, dict):
                return
            if obj.get("type") == "turn.completed":
                usage = obj.get("usage")
                if isinstance(usage, dict):
                    input_tokens = usage.get("input_tokens")
                    cached_input_tokens = usage.get("cached_input_tokens")
                    output_tokens = usage.get("output_tokens")
                    if input_tokens is not None and output_tokens is not None:
                        save_cost_track(
                            model=self._model,
                            input_tokens=int(input_tokens),
                            cached_input_tokens=int(cached_input_tokens or 0),
                            output_tokens=int(output_tokens),
                        )
        except Exception:
            logger.exception("Failed to save token usage")

    def _run_subprocess(
        self,
        *,
        argv: list[str],
        stdin_path: Path,
        log_path: Path,
        events_path: Path,
        started_at: float,
        on_process_started: Callable[[int], None] | None,
        on_stderr_chunk: Callable[[bytes], None] | None,
        on_stdout_jsonl: Callable[[str], None] | None,
        check_termination: Callable[[], bool] | None,
    ) -> tuple[list[str], float, str | None, dict[str, object] | None]:
        """
        Run Codex subprocess and manage I/O.

        Args:
            argv: Command arguments
            log_path: Path to write combined log
            events_path: Path to write JSONL events
            started_at: Timestamp when execution started
            on_process_started: Callback with PID after process starts (or None)
            on_stderr_chunk: Callback for stderr chunks (or None)
            on_stdout_jsonl: Callback for each JSONL line (or None)
            check_termination: Callback to check if should terminate early (or None)

        Returns:
            Tuple of (terminal_output, exec_time, exception_type, exception_info)
        """
        proc: subprocess.Popen[bytes] | None = None
        try:
            with (
                open(stdin_path, "rb") as stdin_file,
                open(log_path, "ab") as logf,
                open(events_path, "ab") as eventsf,
            ):
                proc = subprocess.Popen(
                    args=argv,
                    cwd=str(self._workspace_dir),
                    env=self._env,
                    stdin=stdin_file,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    start_new_session=True,
                    bufsize=0,
                )

                if on_process_started is not None:
                    on_process_started(proc.pid)

                assert proc.stdout is not None
                assert proc.stderr is not None
                stdout_pipe = proc.stdout
                stderr_pipe = proc.stderr

                sel = selectors.DefaultSelector()
                sel.register(stdout_pipe, selectors.EVENT_READ, data="stdout")
                sel.register(stderr_pipe, selectors.EVENT_READ, data="stderr")
                stdout_buf = b""

                while True:
                    if check_termination is not None and check_termination():
                        logger.info("Codex run terminated by external request (pid=%s)", proc.pid)
                        terminate_process_group(pid=proc.pid, grace_seconds=1.0)
                        return self._build_result_from_log(
                            events_path=events_path,
                            started_at=started_at,
                            exc_type="Terminated",
                            exc_info={"reason": "terminated"},
                        )

                    for key, _ in sel.select(timeout=0.1):
                        stream = cast(IO[bytes], key.fileobj)
                        chunk = stream.read(4096)
                        if not chunk:
                            continue
                        logf.write(chunk)
                        logf.flush()

                        if key.data == "stderr":
                            if on_stderr_chunk is not None:
                                on_stderr_chunk(chunk)
                            continue

                        # Process stdout JSONL
                        stdout_buf += chunk
                        while b"\n" in stdout_buf:
                            raw_line, stdout_buf = stdout_buf.split(b"\n", 1)
                            json_line = raw_line + b"\n"
                            eventsf.write(json_line)
                            eventsf.flush()
                            line_str = json_line.decode("utf-8", errors="replace").rstrip("\n")
                            self._save_token_usage_from_jsonl(line_str)
                            if on_stdout_jsonl is not None:
                                on_stdout_jsonl(line_str)

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

    def run_autonomous(
        self,
        *,
        task_file: Path,
    ) -> tuple[list[str], float, str | None, dict[str, object] | None]:
        """
        Run Codex CLI for standalone tasks (e.g., paper writing, metrics generation).

        Simplified interface without tree search context, callbacks, or termination checking.

        Args:
            task_file: Path to the task file containing the prompt

        Returns:
            Tuple of (terminal_output, exec_time, exception_type, exception_info)
        """
        started_at = time.monotonic()
        log_path = self._workspace_dir / self._session_log_name
        events_path = self._workspace_dir / self._events_log_name
        log_path.parent.mkdir(parents=True, exist_ok=True)

        argv = self._build_argv()
        logger.info(
            "Starting Codex CLI (autonomous): %s (cwd=%s)", " ".join(argv), self._workspace_dir
        )

        # Log stderr output in real-time for visibility
        def on_stderr_chunk(chunk: bytes) -> None:
            try:
                decoded_chunk = chunk.decode("utf-8", errors="replace").rstrip()
                if decoded_chunk:
                    logger.info("Codex: %s", decoded_chunk)
            except (ValueError, TypeError):
                pass

        # Log JSONL events in real-time for visibility
        def on_stdout_jsonl(line: str) -> None:
            logger.debug("Codex execution %s", line)

        return self._run_subprocess(
            argv=argv,
            stdin_path=task_file,
            log_path=log_path,
            events_path=events_path,
            started_at=started_at,
            on_process_started=None,
            on_stderr_chunk=on_stderr_chunk,
            on_stdout_jsonl=on_stdout_jsonl,
            check_termination=None,
        )

    def run(
        self,
        *,
        task_file: Path,
        stage: str,
        node: int,
        pid_callback: Callable[[int], None] | None,
        termination_checker: Callable[[], bool] | None,
        json_event_callback: Callable[[str, dict[str, object]], None] | None,
    ) -> tuple[list[str], float, str | None, dict[str, object] | None]:
        """
        Run Codex CLI inside workspace_dir using a task file (low-level interface).

        This runner assumes Codex is invoked in a non-interactive mode. If Codex blocks
        waiting for user input, it will consume the wall-clock timeout and be killed.

        For standalone tasks (paper writing, metrics), prefer run_autonomous() instead.

        Args:
            task_file: Path to the task file containing the prompt
            stage: Stage name for event emission (e.g., "paper_writeup", "stage1")
            node: Node index for tree search contexts
            pid_callback: Callback invoked with the process PID (or None)
            termination_checker: Callback to check if execution should be terminated (or None)
            json_event_callback: Callback for raw JSON events (or None)

        Returns:
            Tuple of (terminal_output, exec_time, exception_type, exception_info)
        """
        started_at = time.monotonic()
        log_path = self._workspace_dir / self._session_log_name
        events_path = self._workspace_dir / self._events_log_name
        log_path.parent.mkdir(parents=True, exist_ok=True)

        argv = self._build_argv()
        logger.info("Starting Codex CLI: %s (cwd=%s)", " ".join(argv), self._workspace_dir)

        # Define callbacks for event emission
        def on_stderr_chunk(chunk: bytes) -> None:
            try:
                decoded_chunk = chunk.decode("utf-8", errors="replace").rstrip()
                self._event_callback(
                    CodexEvent(
                        stage=stage,
                        node=node,
                        event_type="stderr",
                        event_content=decoded_chunk,
                        occurred_at=datetime.now(timezone.utc),
                    )
                )
            except (ValueError, TypeError):
                pass

        def on_stdout_jsonl(line: str) -> None:
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                return
            if not isinstance(obj, dict):
                return
            if json_event_callback is not None:
                json_event_callback(line, obj)
            typ = obj.get("type")
            if typ is not None:
                self._event_callback(
                    CodexEvent(
                        stage=stage,
                        node=node,
                        event_type=typ,
                        event_content=line,
                        occurred_at=datetime.now(timezone.utc),
                    )
                )

        return self._run_subprocess(
            argv=argv,
            stdin_path=task_file,
            log_path=log_path,
            events_path=events_path,
            started_at=started_at,
            on_process_started=pid_callback,
            on_stderr_chunk=on_stderr_chunk,
            on_stdout_jsonl=on_stdout_jsonl,
            check_termination=termination_checker,
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
