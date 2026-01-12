import json
import subprocess
from pathlib import Path


def run_codex_exec_with_output_schema(
    *,
    workspace_dir: Path,
    prompt: str,
    output_schema_path: Path,
    timeout_seconds: int,
    env: dict[str, str],
) -> dict[str, object]:
    """
    Run `codex exec` in non-interactive mode and parse JSON stdout.
    """
    try:
        result = subprocess.run(
            [
                "codex",
                "exec",
                "--full-auto",
                "--sandbox",
                "danger-full-access",
                "--skip-git-repo-check",
                "--output-schema",
                str(output_schema_path),
                prompt,
            ],
            cwd=str(workspace_dir),
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("`codex` not found in PATH; cannot run Codex CLI.") from exc

    if result.returncode != 0:
        raise RuntimeError(
            "Codex exec failed. "
            f"returncode={result.returncode} stderr_tail={result.stderr[-500:]}"
        )

    try:
        parsed = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Codex output was not JSON: {result.stdout[:500]}") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError(f"Codex output was not a JSON object: {parsed!r}")
    return parsed
