import os
import subprocess
from pathlib import Path


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
