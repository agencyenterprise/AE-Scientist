import argparse
import json
import os
import selectors
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import IO, cast

RESEARCH_PIPELINE_ROOT = Path(__file__).resolve().parents[1]
if str(RESEARCH_PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(RESEARCH_PIPELINE_ROOT))


def _build_research_pipeline_venv_env(*, research_pipeline_root: Path) -> dict[str, str]:
    """
    Force Codex and any subprocesses it spawns to prefer the research_pipeline venv.
    This mirrors the safety guardrails we use in the worker pipeline.
    """
    venv_dir = research_pipeline_root / ".venv"
    venv_bin = venv_dir / "bin"
    if not (venv_bin / "python").exists():
        raise FileNotFoundError(
            f"Expected venv python at {venv_bin / 'python'}. "
            "Create it first (e.g. `cd research_pipeline && python -m venv .venv`)."
        )
    env = os.environ.copy()
    env["VIRTUAL_ENV"] = str(venv_dir)
    env["PATH"] = f"{venv_bin}{os.pathsep}{env.get('PATH', '')}"
    env["PIP_REQUIRE_VIRTUALENV"] = "1"
    env["PYTHONNOUSERSITE"] = "1"
    # Make Codex CLI behave in non-interactive / CI-like mode as much as possible.
    # This avoids hanging on update prompts or interactive onboarding screens.
    env["CI"] = "1"
    env["NO_UPDATE_NOTIFIER"] = "1"
    env["DISABLE_UPDATE_NOTIFIER"] = "1"
    env["npm_config_update_notifier"] = "false"
    return env


def _tail_lines(path: Path, *, max_lines: int) -> str:
    if not path.exists():
        return ""
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    tail = lines[-max_lines:] if max_lines > 0 else lines
    return "\n".join(tail)


def _run_codex_exec(
    *,
    workspace_dir: Path,
    prompt: str,
    timeout_seconds: int,
    env: dict[str, str],
    stream_progress: bool,
    stream_jsonl: bool,
) -> tuple[float, int, Path, Path]:
    """
    Run Codex in non-interactive mode via `codex exec`.

    When `--json` is enabled, stdout becomes a JSON Lines (JSONL) stream so we can capture
    every event Codex emits while it’s running (machine-readable automation).
    See: https://developers.openai.com/codex/noninteractive
    """
    started_at = time.monotonic()
    log_path = workspace_dir / "codex_session.log"
    jsonl_path = workspace_dir / "codex_events.jsonl"

    argv = [
        "codex",
        "exec",
        "--full-auto",
        "--sandbox",
        "danger-full-access",
        "--skip-git-repo-check",
        "--json",
        prompt,
    ]

    proc = subprocess.Popen(
        argv,
        cwd=str(workspace_dir),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=False,
        bufsize=0,
    )

    assert proc.stdout is not None
    assert proc.stderr is not None

    stdout_pipe = proc.stdout
    stderr_pipe = proc.stderr

    sel = selectors.DefaultSelector()
    sel.register(stdout_pipe, selectors.EVENT_READ, data="stdout")
    sel.register(stderr_pipe, selectors.EVENT_READ, data="stderr")
    stdout_buf = b""
    stderr_buf = b""

    with open(log_path, "wb") as logf, open(jsonl_path, "wb") as jsonlf:
        while True:
            if time.monotonic() - started_at > float(timeout_seconds):
                proc.terminate()
                time.sleep(0.5)
                proc.kill()
                break

            if proc.poll() is not None:
                # Drain any remaining bytes after exit.
                for key, _ in sel.select(timeout=0):
                    stream = cast(IO[bytes], key.fileobj)
                    data = stream.read()
                    if not data:
                        continue
                    if key.data == "stdout":
                        stdout_buf += data
                    else:
                        stderr_buf += data
                break

            events = sel.select(timeout=0.1)
            for key, _ in events:
                stream = cast(IO[bytes], key.fileobj)
                chunk = stream.read(4096)
                if not chunk:
                    continue
                if key.data == "stdout":
                    stdout_buf += chunk
                    while b"\n" in stdout_buf:
                        line, stdout_buf = stdout_buf.split(b"\n", 1)
                        json_line = line + b"\n"
                        jsonlf.write(json_line)
                        jsonlf.flush()
                        logf.write(json_line)
                        logf.flush()
                        if stream_jsonl:
                            sys.stdout.write(json_line.decode("utf-8", errors="replace"))
                            sys.stdout.flush()
                else:
                    stderr_buf += chunk
                    # Log stderr as raw bytes, but only stream to terminal if requested.
                    logf.write(chunk)
                    logf.flush()
                    if stream_progress:
                        sys.stderr.write(chunk.decode("utf-8", errors="replace"))
                        sys.stderr.flush()

        # Flush any partial remaining buffers.
        if stdout_buf:
            jsonlf.write(stdout_buf)
            jsonlf.flush()
            logf.write(stdout_buf)
            logf.flush()
            if stream_jsonl:
                sys.stdout.write(stdout_buf.decode("utf-8", errors="replace"))
                sys.stdout.flush()
        if stderr_buf:
            logf.write(stderr_buf)
            logf.flush()
            if stream_progress:
                sys.stderr.write(stderr_buf.decode("utf-8", errors="replace"))
                sys.stderr.flush()

    exec_time = time.monotonic() - started_at
    returncode = proc.returncode if proc.returncode is not None else -1
    return exec_time, int(returncode), log_path, jsonl_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Codex CLI can perform a simple task.")
    parser.add_argument("--timeout", type=int, default=60, help="Wall-clock timeout in seconds.")
    parser.add_argument("--keep-dir", action="store_true", help="Print workspace dir path on exit.")
    parser.add_argument(
        "--no-stream-progress",
        action="store_true",
        help="Do not stream Codex progress to stdout (still writes codex_session.log).",
    )
    parser.add_argument(
        "--no-stream-jsonl",
        action="store_true",
        help="Do not stream Codex JSONL events to stdout (still writes codex_events.jsonl).",
    )
    args = parser.parse_args()

    codex_path = shutil.which("codex")
    if not codex_path:
        print("ERROR: `codex` not found in PATH. Install it (e.g. `npm i -g @openai/codex`).")
        return 2

    try:
        codex_env = _build_research_pipeline_venv_env(research_pipeline_root=RESEARCH_PIPELINE_ROOT)
    except (FileNotFoundError, OSError, RuntimeError) as exc:
        print(f"ERROR: could not configure research_pipeline venv environment: {exc}")
        return 2

    if args.keep_dir:
        workspace_dir = Path(
            tempfile.mkdtemp(prefix="ae_scientist_codex_validate_", dir="/tmp")
        ).resolve()
        print(f"workspace_dir={workspace_dir}")
    else:
        workspace_dir = Path(tempfile.mkdtemp(prefix="ae_scientist_codex_validate_")).resolve()
    try:
        task_file = workspace_dir / "codex_task.md"
        output_json = workspace_dir / "result.json"
        proof_txt = workspace_dir / "proof.txt"

        # Keep a copy of what we asked Codex to do on disk.
        prompt = (
            "Create two files in the current directory.\n"
            f"1) Create `{proof_txt.name}` with exact contents: ok\n"
            f'2) Create `{output_json.name}` with exact JSON: {{"status": "ok"}}\n'
            "Do not ask the user for input.\n"
        )
        task_file.write_text(prompt, encoding="utf-8")

        exec_time, returncode, log_path, jsonl_path = _run_codex_exec(
            workspace_dir=workspace_dir,
            prompt=prompt,
            timeout_seconds=args.timeout,
            env=codex_env,
            stream_progress=not args.no_stream_progress,
            stream_jsonl=not args.no_stream_jsonl,
        )

        if returncode != 0:
            print(f"Codex failed: returncode={returncode} exec_time={exec_time:.2f}s")
            print("\n--- codex_session.log (tail) ---")
            print(_tail_lines(log_path, max_lines=200))
            return 1

        if (
            not proof_txt.exists()
            or proof_txt.read_text(encoding="utf-8", errors="replace").strip() != "ok"
        ):
            print("Codex did not create proof.txt with expected contents.")
            print("\n--- codex_session.log (tail) ---")
            print(_tail_lines(log_path, max_lines=200))
            return 1

        if not output_json.exists():
            print("Codex did not create result.json.")
            print("\n--- codex_session.log (tail) ---")
            print(_tail_lines(log_path, max_lines=200))
            return 1

        try:
            parsed = json.loads(output_json.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            parsed = None
        if parsed != {"status": "ok"}:
            print(f"Codex created result.json but contents were unexpected: {parsed!r}")
            print("\n--- codex_session.log (tail) ---")
            print(_tail_lines(log_path, max_lines=200))
            return 1

        print(f"\nOK: Codex created files successfully (exec_time={exec_time:.2f}s).")
        print(f"\nSaved JSONL events to: {jsonl_path}")
        print(f"proof.txt: {proof_txt.read_text(encoding='utf-8', errors='replace').strip()!r}")
        print(f"result.json: {output_json.read_text(encoding='utf-8', errors='replace').strip()!r}")
        return 0
    finally:
        if not args.keep_dir:
            shutil.rmtree(workspace_dir, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
