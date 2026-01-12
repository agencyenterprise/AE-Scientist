import os
import subprocess
import sys
from pathlib import Path


def ensure_codex_venv(*, research_pipeline_root: Path) -> Path:
    """
    Ensure a shared venv exists for the research_pipeline codebase.

    We intentionally avoid creating per-workspace venvs (e.g. per process workspace) because that
    leads to repeated installs across runs. Instead, Codex is run with env vars that point to this
    shared venv so `python` / `pip` resolve consistently.
    """
    venv_dir = research_pipeline_root / ".venv"
    venv_python = venv_dir / "bin" / "python"
    if venv_python.exists():
        return venv_dir
    subprocess.run(
        [sys.executable, "-m", "venv", str(venv_dir)],
        check=True,
        cwd=str(research_pipeline_root),
        env=os.environ.copy(),
        capture_output=True,
        text=True,
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
