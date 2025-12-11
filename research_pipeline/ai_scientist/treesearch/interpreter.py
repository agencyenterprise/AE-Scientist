"""
Python interpreter for executing code snippets and capturing their output.
Supports:
- captures stdout and stderr
- captures exceptions and stack traces
- limits execution time
"""

import logging
import multiprocessing
import os
import queue
import signal
import subprocess
import sys
import time
import traceback
import warnings
from dataclasses import dataclass
from multiprocessing import Queue
from multiprocessing.context import SpawnProcess
from pathlib import Path
from typing import Any

import humanize
import IPython.core.ultratb
import shutup  # type: ignore[import-untyped]
from dataclasses_json import DataClassJsonMixin

logger = logging.getLogger("ai-scientist")

try:
    multiprocessing.set_start_method("spawn", force=True)
except RuntimeError:
    pass


def _project_root() -> Path:
    """
    Best-effort repository root used for PYTHONPATH when spawning a different interpreter.
    Assumes this file lives under <root>/ai_scientist/treesearch/interpreter.py.
    """
    root = Path(__file__).resolve().parents[2]
    logger.debug(f"_project_root resolved to {root}")
    return root


def _managed_venv_dir(working_dir: Path) -> Path:
    """
    Directory where the interpreter-managed virtual environment is created.
    """
    venv_dir = working_dir / ".ai_scientist_venv"
    logger.debug(f"Managed venv directory set to {venv_dir}")
    return venv_dir


def _venv_python_path(venv_dir: Path) -> Path:
    """
    Resolve the python executable for the managed venv on Linux.
    Assumes `uv venv` created `<venv_dir>/bin/python`.
    """
    python_path = venv_dir / "bin" / "python"
    if python_path.exists():
        logger.debug(f"Resolved venv python at {python_path}")
        return python_path
    raise FileNotFoundError(f"Python executable not found in venv at {venv_dir}")


def _run_uv(
    *, args: list[str], timeout_seconds: int, extra_env: dict[str, str], cwd: Path
) -> subprocess.CompletedProcess:
    """
    Helper to run `uv <args...>` with consistent settings.
    """
    env = os.environ.copy()
    for key, value in extra_env.items():
        env[key] = value
    cmd_display = " ".join(["uv", *args])
    logger.debug(f"Running uv command: {cmd_display} (cwd={cwd})")
    try:
        proc = subprocess.run(
            args=["uv", *args],
            check=True,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            env=env,
            cwd=str(cwd),
        )
    except subprocess.CalledProcessError as exc:
        logger.error(
            "uv command failed: %s (cwd=%s, returncode=%d)\nstdout:\n%s\nstderr:\n%s",
            cmd_display,
            cwd,
            exc.returncode,
            exc.stdout,
            exc.stderr,
        )
        raise

    logger.debug(
        "uv command completed: %s (stdout_len=%d, stderr_len=%d)",
        cmd_display,
        len(proc.stdout),
        len(proc.stderr),
    )
    return proc


def _ensure_managed_venv(*, working_dir: Path, timeout_seconds: int) -> Path:
    """
    Create (if needed) and populate a managed virtual environment mirroring the current env.
    Returns the path to the managed venv's python executable.
    """
    venv_dir = _managed_venv_dir(working_dir)
    logger.debug(
        "Ensuring managed venv (working_dir=%s, venv_dir=%s, timeout=%d)",
        working_dir,
        venv_dir,
        timeout_seconds,
    )
    if not venv_dir.exists():
        logger.debug(f"Creating managed venv via uv venv --system-site-packages at {venv_dir}")
        _run_uv(
            args=["venv", "--system-site-packages", str(venv_dir)],
            timeout_seconds=timeout_seconds,
            extra_env={},
            cwd=working_dir,
        )
    else:
        logger.debug(f"Reusing existing managed venv at {venv_dir}")

    venv_python = _venv_python_path(venv_dir)

    # Install project dependencies from pyproject.toml using `uv sync`
    project_root = _project_root()
    src_pyproject = project_root / "pyproject.toml"
    dst_pyproject = working_dir / "pyproject.toml"
    if src_pyproject.exists():
        logger.debug(f"Copying pyproject.toml from {src_pyproject} to {dst_pyproject}")
        dst_pyproject.write_text(src_pyproject.read_text(encoding="utf-8"), encoding="utf-8")
    else:
        logger.debug(f"No pyproject.toml found at {src_pyproject}; proceeding without copy")
    # Copy uv.lock if present to keep resolution consistent
    src_lock = project_root / "uv.lock"
    dst_lock = working_dir / "uv.lock"
    if src_lock.exists():
        logger.debug(f"Copying uv.lock from {src_lock} to {dst_lock}")
        dst_lock.write_text(src_lock.read_text(encoding="utf-8"), encoding="utf-8")
    else:
        logger.debug(f"No uv.lock found at {src_lock}; uv will resolve dependencies")
    logger.debug(f"Syncing project dependencies with uv (cwd={working_dir}, python={venv_python})")
    _run_uv(
        args=["sync"],
        timeout_seconds=max(timeout_seconds, 600),
        extra_env={
            "UV_PROJECT_ENVIRONMENT": str(venv_dir),
            "UV_PYTHON": str(venv_python),
        },
        cwd=working_dir,
    )
    logger.debug(f"Managed venv ready (python={venv_python})")

    return venv_python


@dataclass
class ExecutionResult(DataClassJsonMixin):
    """
    Result of executing a code snippet in the interpreter.
    Contains the output, execution time, and exception information.
    """

    term_out: list[str]
    exec_time: float
    exc_type: str | None
    exc_info: dict | None = None
    exc_stack: list[tuple] | None = None


def exception_summary(
    e: Exception, working_dir: Path, exec_file_name: str, format_tb_ipython: bool
) -> tuple[str, str, dict[str, Any], list[tuple[str, int, str, str | None]]]:
    """
    Generate a summary string for an exception and its stack trace.
    Supports both standard Python REPL and IPython formatting.
    """
    if format_tb_ipython:
        tb = IPython.core.ultratb.VerboseTB(tb_offset=1, color_scheme="NoColor")
        tb_str = str(tb.text(*sys.exc_info()))
    else:
        tb_lines = traceback.format_exception(e)
        # skip parts of stack trace in weflow code
        tb_str = "".join(
            [line for line in tb_lines if "treesearch/" not in line and "importlib" not in line]
        )

    # replace whole path to file with just filename (to remove agent workspace dir)
    tb_str = tb_str.replace(str(working_dir / exec_file_name), exec_file_name)

    exc_info: dict[str, Any] = {}
    if e.args:
        exc_info["args"] = [str(i) for i in e.args]
    details = vars(e)
    for att in ["name", "msg", "obj"]:
        if att in details:
            exc_info[att] = str(details[att])

    tb_stack = traceback.extract_tb(e.__traceback__)
    exc_stack = [(t.filename, t.lineno or 0, t.name, t.line) for t in tb_stack]

    return tb_str, e.__class__.__name__, exc_info, exc_stack


class RedirectQueue:
    def __init__(self, queue: Queue) -> None:
        self.queue: Queue = queue

    def write(self, msg: str) -> None:
        self.queue.put(msg)

    def flush(self) -> None:
        pass


def _repl_run_session(
    *,
    working_dir: str | Path,
    agent_file_name: str,
    format_tb_ipython: bool,
    env_vars: dict[str, str],
    code_inq: Queue,
    result_outq: Queue,
    event_outq: Queue,
) -> None:
    """
    Module-level REPL loop function used as multiprocessing target.
    Using a module-level function avoids pickling the Interpreter instance
    which can fail under the 'spawn' start method.
    """
    # Child process setup (mirrors Interpreter.child_proc_setup)
    shutup.mute_warnings()
    # Suppress PyMuPDF layout warning
    warnings.filterwarnings("ignore", message=".*pymupdf_layout.*", category=UserWarning)
    warnings.filterwarnings("ignore", message="Consider using the pymupdf_layout package.*")

    for key, value in env_vars.items():
        os.environ[key] = str(value)

    wd = Path(working_dir)
    os.chdir(str(wd))
    sys.path.append(str(wd))
    sys.stdout = sys.stderr = RedirectQueue(result_outq)  # type: ignore[assignment,unused-ignore]

    global_scope: dict = {}
    while True:
        code = code_inq.get()
        os.chdir(str(wd))
        with open(agent_file_name, "w") as f:
            f.write(code)

        # Signal to the parent that we are about to execute
        event_outq.put(("state:ready", None, None, None))
        try:
            exec(compile(code, agent_file_name, "exec"), global_scope)
        except BaseException as e:
            if isinstance(e, Exception):
                tb_str, e_cls_name, exc_info, exc_stack = exception_summary(
                    e, wd, agent_file_name, format_tb_ipython
                )
            else:
                tb_str = str(e)
                e_cls_name = e.__class__.__name__
                exc_info = {}
                exc_stack = []
            result_outq.put(tb_str)
            if e_cls_name == "KeyboardInterrupt":
                e_cls_name = "TimeoutError"
            event_outq.put(("state:finished", e_cls_name, exc_info, exc_stack))
        else:
            event_outq.put(("state:finished", None, None, None))

        # EOF marker for parent to stop reading output
        result_outq.put("<|EOF|>")


class Interpreter:
    def __init__(
        self,
        working_dir: Path | str,
        timeout: int = 3600,
        format_tb_ipython: bool = False,
        agent_file_name: str = "runfile.py",
        env_vars: dict[str, str] | None = None,
    ) -> None:
        """
        Simulates a standalone Python REPL with an execution time limit.

        Args:
            working_dir (Path | str): working directory of the agent
        timeout (int, optional): Timeout for each code execution step.
            Defaults to 3600.
        format_tb_ipython (bool, optional): Whether to use IPython or the
            default Python REPL formatting for exceptions. Defaults to False.
        agent_file_name (str, optional): The name for the agent's code file.
            Defaults to "runfile.py".
        env_vars (dict[str, str], optional): Environment variables to set in
            the child process. Defaults to {}.
        """
        # this really needs to be a path, otherwise causes issues that don't raise exc
        self.working_dir = Path(working_dir).resolve()
        assert self.working_dir.exists(), f"Working directory {self.working_dir} does not exist"
        self.timeout = timeout
        self.format_tb_ipython = format_tb_ipython
        self.agent_file_name = agent_file_name
        self.process: SpawnProcess | None = None
        self.env_vars = env_vars or {}
        self.mp_context = multiprocessing.get_context("spawn")
        self._venv_python: Path | None = None
        self.code_inq: Queue[str]
        self.result_outq: Queue[str]
        self.event_outq: Queue[
            tuple[
                str,
                str | None,
                dict[str, Any] | None,
                list[tuple[str, int, str, str | None]] | None,
            ]
        ]

    def child_proc_setup(self, result_outq: Queue) -> None:
        # disable all warnings (before importing anything)
        shutup.mute_warnings()
        # Suppress PyMuPDF layout warning
        warnings.filterwarnings("ignore", message=".*pymupdf_layout.*", category=UserWarning)
        warnings.filterwarnings("ignore", message="Consider using the pymupdf_layout package.*")

        for key, value in self.env_vars.items():
            os.environ[key] = str(value)

        os.chdir(str(self.working_dir))
        logger.debug(
            "Child process environment prepared (cwd=%s, env_overrides=%s)",
            self.working_dir,
            list(self.env_vars.keys()),
        )

        # this seems to only  benecessary because we're exec'ing code from a string,
        # a .py file should be able to import modules from the cwd anyway
        sys.path.append(str(self.working_dir))

        # capture stdout and stderr
        sys.stdout = sys.stderr = RedirectQueue(result_outq)  # type: ignore[assignment,unused-ignore]
        logger.debug("Child process stdio redirected to parent result queue")

    def _run_session(
        self,
        code_inq: Queue,
        result_outq: Queue,
        event_outq: Queue,
    ) -> None:
        self.child_proc_setup(result_outq)

        global_scope: dict = {}
        while True:
            code = code_inq.get()
            os.chdir(str(self.working_dir))
            with open(self.agent_file_name, "w") as f:
                f.write(code)

            event_outq.put(("state:ready", None, None, None))
            try:
                exec(compile(code, self.agent_file_name, "exec"), global_scope)
            except BaseException as e:
                if isinstance(e, Exception):
                    tb_str, e_cls_name, exc_info, exc_stack = exception_summary(
                        e,
                        self.working_dir,
                        self.agent_file_name,
                        self.format_tb_ipython,
                    )
                else:
                    tb_str = str(e)
                    e_cls_name = e.__class__.__name__
                    exc_info = {}
                    exc_stack = []
                result_outq.put(tb_str)
                if e_cls_name == "KeyboardInterrupt":
                    e_cls_name = "TimeoutError"

                event_outq.put(("state:finished", e_cls_name, exc_info, exc_stack))
            else:
                event_outq.put(("state:finished", None, None, None))

            # put EOF marker to indicate that we're done
            result_outq.put("<|EOF|>")

    def create_process(self) -> None:
        # we use three queues to communicate with the child process:
        # - code_inq: send code to child to execute
        # - result_outq: receive stdout/stderr from child
        # - event_outq: receive events from child (e.g. state:ready, state:finished)
        self.code_inq = self.mp_context.Queue()
        self.result_outq = self.mp_context.Queue()
        self.event_outq = self.mp_context.Queue()
        # Prepare managed venv and configure the spawn executable
        if self._venv_python is None:
            # Use a generous timeout for environment setup independent of execution timeout
            setup_timeout = max(900, int(self.timeout))
            logger.debug(
                "Preparing managed venv for child (parent_executable=%s, timeout=%d)",
                sys.executable,
                setup_timeout,
            )
            self._venv_python = _ensure_managed_venv(
                working_dir=self.working_dir, timeout_seconds=setup_timeout
            )

        # Temporarily point multiprocessing to the managed venv's python for this start()
        old_executable = getattr(multiprocessing, "get_executable", lambda: sys.executable)()
        logger.debug(
            f"Setting multiprocessing executable (old={old_executable}, new={self._venv_python})"
        )
        multiprocessing.set_executable(str(self._venv_python))
        try:
            # Use module-level function as target to avoid pickling Interpreter instance
            self.process = self.mp_context.Process(
                target=_repl_run_session,
                kwargs=dict(
                    working_dir=str(self.working_dir),
                    agent_file_name=self.agent_file_name,
                    format_tb_ipython=self.format_tb_ipython,
                    env_vars=self.env_vars,
                    code_inq=self.code_inq,
                    result_outq=self.result_outq,
                    event_outq=self.event_outq,
                ),
            )
            self.process.start()
            logger.debug(
                f"Child process started (pid={self.process.pid}, executable={self._venv_python}, cwd={self.working_dir}, agent_file={self.agent_file_name})"
            )
        finally:
            multiprocessing.set_executable(str(old_executable))
            logger.debug(f"Restored multiprocessing executable to {old_executable}")

    def _drain_queues(self) -> None:
        """Quickly drain all in-flight messages to prevent blocking."""
        while not self.result_outq.empty():
            try:
                self.result_outq.get_nowait()
            except Exception:
                break

        while not self.event_outq.empty():
            try:
                self.event_outq.get_nowait()
            except Exception:
                break

        while not self.code_inq.empty():
            try:
                self.code_inq.get_nowait()
            except Exception:
                break

    def cleanup_session(self) -> None:
        if self.process is None:
            return
        # give the child process a chance to terminate gracefully
        logger.debug(f"Terminating child process (pid={self.process.pid})")
        self.process.terminate()
        self._drain_queues()
        self.process.join(timeout=2)
        # kill the child process if it's still alive
        if self.process.exitcode is None:
            logger.warning("Child process failed to terminate gracefully, killing it..")
            self.process.kill()
            self._drain_queues()
            self.process.join(timeout=2)
        # don't wait for gc, clean up immediately
        self.process.close()
        logger.debug("Child process resources released")
        self.process = None

    def run(self, code: str, reset_session: bool = True) -> ExecutionResult:
        """
        Execute the provided Python command in a separate process and return its output.

        Parameters:
            code (str): Python code to execute.
            reset_session (bool, optional): Whether to reset the interpreter session before executing the code. Defaults to True.

        Returns:
            ExecutionResult: Object containing the output and metadata of the code execution.

        """

        logger.debug(
            f"Interpreter.run called (reset_session={reset_session}, timeout={self.timeout}, parent_executable={sys.executable})"
        )
        logger.debug("Starting Python interpreter process...")

        if reset_session:
            if self.process is not None:
                # terminate and clean up previous process
                self.cleanup_session()
            self.create_process()
            logger.debug("✓ Interpreter ready, sending code to execute")
        else:
            # reset_session needs to be True on first exec
            if self.process is None:
                raise RuntimeError("Process is not initialized")

        if self.process is None:
            raise RuntimeError("Process is not initialized")

        assert self.process.is_alive()

        self.code_inq.put(code)
        logger.debug(f"Submitted code to child (chars={len(code)})")

        # wait for child to actually start execution (we don't want interrupt child setup)
        startup_deadline = time.time() + float(os.environ.get("AI_SCI_STARTUP_TIMEOUT", "300"))
        state = None
        while True:
            remaining = startup_deadline - time.time()
            if remaining <= 0:
                msg = "REPL child process failed to start execution"
                logger.critical(msg)
                if self.process is not None and not self.process.is_alive():
                    logger.critical(
                        f"REPL child died before start (pid={self.process.pid}, exitcode={self.process.exitcode})"
                    )
                while not self.result_outq.empty():
                    logger.error(f"REPL output queue dump: {self.result_outq.get()}")
                raise RuntimeError(msg) from None
            try:
                state = self.event_outq.get(timeout=min(1.0, max(0.0, remaining)))
                break
            except queue.Empty:
                if self.process is not None and not self.process.is_alive():
                    msg = "REPL child process died before signaling readiness"
                    logger.critical(msg)
                    while not self.result_outq.empty():
                        logger.error(f"REPL output queue dump: {self.result_outq.get()}")
                    raise RuntimeError(msg) from None
                continue
        assert state[0] == "state:ready", state
        start_time = time.time()
        logger.debug("Code is now executing...")
        last_progress_time = start_time

        # this flag indicates that the child ahs exceeded the time limit and an interrupt was sent
        # if the child process dies without this flag being set, it's an unexpected termination
        child_in_overtime = False

        while True:
            try:
                # check if the child is done
                state = self.event_outq.get(timeout=1)  # wait for state:finished
                assert state[0] == "state:finished", state
                exec_time = time.time() - start_time
                break
            except queue.Empty:
                # Print progress update every 30 seconds
                current_time = time.time()
                if current_time - last_progress_time >= 30:
                    elapsed = current_time - start_time
                    logger.debug(f"Still executing... ({humanize.naturaldelta(elapsed)} elapsed)")
                    last_progress_time = current_time

                # we haven't heard back from the child -> check if it's still alive (assuming overtime interrupt wasn't sent yet)
                if (
                    self.process is not None
                    and not child_in_overtime
                    and not self.process.is_alive()
                ):
                    msg = "REPL child process died unexpectedly"
                    logger.critical(msg)
                    while not self.result_outq.empty():
                        logger.error(f"REPL output queue dump: {self.result_outq.get()}")
                    raise RuntimeError(msg) from None

                # child is alive and still executing -> check if we should sigint..
                if self.timeout is None:
                    continue  # type: ignore[unreachable]
                running_time = time.time() - start_time
                if running_time > self.timeout:
                    # [TODO] handle this in a better way
                    assert reset_session, "Timeout ocurred in interactive session"

                    # send interrupt to child
                    if self.process is not None and self.process.pid is not None:
                        os.kill(self.process.pid, signal.SIGINT)
                    child_in_overtime = True
                    # terminate if we're overtime by more than a minute
                    if running_time > self.timeout + 60:
                        logger.warning("Child failed to terminate, killing it..")
                        self.cleanup_session()

                        state = ("state:finished", "TimeoutError", {}, [])
                        exec_time = self.timeout
                        break

        output: list[str] = []
        # read all stdout/stderr from child up to the EOF marker
        # waiting until the queue is empty is not enough since
        # the feeder thread in child might still be adding to the queue
        while not self.result_outq.empty() or not output or output[-1] != "<|EOF|>":
            output.append(self.result_outq.get())
        output.pop()  # remove the EOF marker
        logger.debug(f"Collected {len(output)} output segments from child")

        # Filter out PyMuPDF layout warning messages
        output = [
            line
            for line in output
            if "pymupdf_layout" not in line.lower()
            and "Consider using the pymupdf_layout package" not in line
        ]

        e_cls_name = state[1] if len(state) > 1 else None
        exc_info = state[2] if len(state) > 2 else None
        exc_stack = state[3] if len(state) > 3 else None

        if e_cls_name == "TimeoutError":
            output.append(
                f"TimeoutError: Execution exceeded the time limit of {humanize.naturaldelta(self.timeout)}"
            )
        else:
            output.append(
                f"Execution time: {humanize.naturaldelta(exec_time)} seconds (time limit is {humanize.naturaldelta(self.timeout)})."
            )
        logger.debug(f"Child execution completed (exc_type={e_cls_name}, exec_time={exec_time})")
        return ExecutionResult(output, exec_time, e_cls_name, exc_info, exc_stack)
