import json
import logging
import selectors
import subprocess
import time
from pathlib import Path
from typing import IO, Callable, Sequence, cast

from ..process_utils import terminate_process_group

logger = logging.getLogger("ai-scientist")


class CodexCliRunner:
    def __init__(
        self,
        *,
        workspace_dir: Path,
        session_log_name: str,
        events_log_name: str,
        timeout_seconds: int,
        argv: Sequence[str],
        env: dict[str, str],
    ) -> None:
        self._workspace_dir = workspace_dir
        self._session_log_name = session_log_name
        self._events_log_name = events_log_name
        self._timeout_seconds = timeout_seconds
        self._argv = list(argv)
        self._env = dict(env)

    def run(
        self,
        *,
        task_file: Path,
        pid_callback: Callable[[int], None] | None,
        termination_checker: Callable[[], bool] | None,
        stream_callback: Callable[[str], None] | None = None,
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
        argv = [*self._argv, prompt]
        logger.info("Starting Codex CLI: %s (cwd=%s)", " ".join(argv[:3]), self._workspace_dir)

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

                def _emit(msg: str) -> None:
                    if stream_callback is None:
                        return
                    try:
                        stream_callback(msg)
                    except (OSError, RuntimeError, ValueError, TypeError):
                        # Never fail the run because the UI/event sink failed.
                        return

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
                        _emit(f"[codex:error] {line}")
                        return
                    if typ in ("thread.started", "turn.started", "turn.completed", "turn.failed"):
                        _emit(f"[codex:{typ}] {line}")
                        return
                    item = obj.get("item")
                    if not isinstance(item, dict):
                        return
                    item_type = item.get("type")
                    if item_type == "agent_message":
                        text = item.get("text")
                        if isinstance(text, str):
                            _emit(f"[codex:agent_message] {text}")
                        return
                    if item_type == "command_execution":
                        cmd = item.get("command")
                        status = item.get("status")
                        if isinstance(cmd, str):
                            cmd_one_line = " ".join(cmd.splitlines())
                            _emit(f"[codex:cmd:{status}] {cmd_one_line[:400]}")
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
                                _emit(
                                    f"[codex:stderr] {chunk.decode('utf-8', errors='replace').rstrip()}"
                                )
                            except (OSError, RuntimeError, ValueError, TypeError):
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
