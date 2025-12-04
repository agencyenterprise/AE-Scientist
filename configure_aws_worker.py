#!/usr/bin/env python3
"""Bootstrap an AWS EC2 research worker from a pasted SSH command."""

from __future__ import annotations

import argparse
import shlex
import subprocess
import sys
from pathlib import Path

DEFAULT_WORKSPACE_REPO = Path.home() / "workspace" / "AE-Scientist"
DEFAULT_ENV_PATH = DEFAULT_WORKSPACE_REPO / "research_pipeline" / ".env"
SSH_CONFIG_PATH = Path.home() / ".ssh" / "config"


class SSHCommandParseError(ValueError):
    """Raised when a pasted SSH command cannot be parsed."""


def _parse_ssh_command(command: str) -> tuple[str, str, Path, str]:
    tokens = shlex.split(command)
    key_path = Path("~/.ssh/ae-alignment-newton.pem").expanduser()
    port = "22"
    user: str | None = None
    host: str | None = None

    iterator = iter(range(len(tokens)))
    for idx in iterator:
        token = tokens[idx]
        if token == "ssh":
            continue
        if token == "-p":
            try:
                port = tokens[idx + 1]
            except IndexError as exc:
                raise SSHCommandParseError("Missing value after -p") from exc
            next(iterator, None)
            continue
        if token.startswith("-"):
            continue
        if "@" in token and user is None:
            user, host = token.split("@", 1)
            continue

    if user is None or host is None:
        raise SSHCommandParseError("Could not extract user@host from SSH command.")
    return user, host, key_path, port


def _run_step(description: str, *args: str) -> None:
    print(f"==> {description}")
    subprocess.run(args, check=True)
    print()


def _ensure_ssh_config_entry(
    hostname: str, user: str, port: str, identity_file: Path
) -> None:
    SSH_CONFIG_PATH.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    SSH_CONFIG_PATH.touch(mode=0o600, exist_ok=True)
    existing = [
        line.strip()
        for line in SSH_CONFIG_PATH.read_text(encoding="utf-8").splitlines()
        if line.startswith("Host AWS-WORKER-")
    ]
    next_index = 1
    if existing:
        suffixes = [
            int(line.split("-")[-1])
            for line in existing
            if line.split("-")[-1].isdigit()
        ]
        if suffixes:
            next_index = max(suffixes) + 1
    alias = f"AWS-WORKER-{next_index}"
    with SSH_CONFIG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(
            f"Host {alias}\n"
            f"  HostName {hostname}\n"
            f"  User {user}\n"
            f"  Port {port}\n"
            f"  IdentityFile {identity_file}\n\n"
        )
    SSH_CONFIG_PATH.chmod(0o600)
    print(f"Added SSH config entry: {alias}")
    print()


def _remote_cmd(script: str) -> str:
    return "bash -lc " + shlex.quote(script)


def _bootstrap_remote(
    *,
    user: str,
    host: str,
    port: str,
    key_path: Path,
    git_user: str,
    git_email: str,
) -> None:
    remote = """
set -euo pipefail
export PATH="$HOME/.local/bin:$PATH"
if [ -f /opt/pytorch/bin/activate ]; then
  source /opt/pytorch/bin/activate
fi
if ! command -v uv >/dev/null 2>&1; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi
PYTORCH_PYTHON="/opt/pytorch/bin/python3.12"
PYTORCH_SITE_PACKAGES="/opt/pytorch/lib/python3.12/site-packages"
if [ ! -x "$PYTORCH_PYTHON" ]; then
  echo "ERROR: Expected Python interpreter $PYTORCH_PYTHON not found." >&2
  exit 1
fi
if [ ! -d "$PYTORCH_SITE_PACKAGES" ]; then
  echo "ERROR: Expected site-packages directory $PYTORCH_SITE_PACKAGES not found." >&2
  exit 1
fi
sudo mkdir -p /workspace
sudo chown "$USER":"$USER" /workspace
cd /workspace
if [ -d AE-Scientist ]; then
  echo 'Repository already present. Pulling latest changes...'
  cd AE-Scientist
  git pull --rebase
else
  echo 'Cloning AE-Scientist repository...'
  git clone git@github.com:agencyenterprise/AE-Scientist.git
  cd AE-Scientist
fi
cd research_pipeline
uv venv --python="$PYTORCH_PYTHON" --system-site-packages
source .venv/bin/activate
export PYTHONPATH="$PYTORCH_SITE_PACKAGES:${PYTHONPATH:-}"
uv sync
cd ..
git config --global user.email {git_email}
git config --global user.name {git_user}
git config --global core.editor vim
git config --global push.autoSetupRemote true
"""
    remote = remote.format(
        git_email=shlex.quote(git_email), git_user=shlex.quote(git_user)
    )
    _run_step(
        "Bootstrapping remote worker",
        "ssh",
        "-i",
        str(key_path),
        "-p",
        port,
        f"{user}@{host}",
        _remote_cmd(remote),
    )


def _copy_env_file(
    *,
    user: str,
    host: str,
    port: str,
    key_path: Path,
    env_path: Path,
) -> None:
    if not env_path.exists():
        raise FileNotFoundError(f"Local env file not found: {env_path}")
    _run_step(
        "Copying .env to remote worker",
        "scp",
        "-i",
        str(key_path),
        "-P",
        port,
        str(env_path),
        f"{user}@{host}:/workspace/AE-Scientist/research_pipeline/.env",
    )


def configure_worker(args: argparse.Namespace) -> None:
    try:
        user, host, key_path, port = _parse_ssh_command(args.ssh_command)
    except SSHCommandParseError as exc:
        raise SystemExit(f"Failed to parse SSH command: {exc}") from exc

    if not key_path.exists():
        raise SystemExit(f"SSH key not found: {key_path}")

    print("==> Testing SSH connectivity...")
    subprocess.run(
        [
            "ssh",
            "-o",
            "StrictHostKeyChecking=no",
            "-i",
            str(key_path),
            "-p",
            port,
            f"{user}@{host}",
            "echo 'SSH key auth successful.'",
        ],
        check=True,
    )
    print()

    _ensure_ssh_config_entry(host, user, port, key_path)

    print("==> Installing GitHub host key on worker...")
    remote_known_hosts = """
mkdir -p ~/.ssh
ssh-keyscan github.com >> ~/.ssh/known_hosts
chmod 644 ~/.ssh/known_hosts
"""
    _run_step(
        "Scanning GitHub host key",
        "ssh",
        "-i",
        str(key_path),
        "-p",
        port,
        f"{user}@{host}",
        _remote_cmd(remote_known_hosts),
    )

    _bootstrap_remote(
        user=user,
        host=host,
        port=port,
        key_path=key_path,
        git_user=args.git_name,
        git_email=args.git_email,
    )

    _copy_env_file(
        user=user,
        host=host,
        port=port,
        key_path=key_path,
        env_path=args.env_path,
    )

    print("==> AWS worker configuration complete!")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Configure an AWS EC2 worker for AE Scientist pipeline runs."
    )
    parser.add_argument(
        "ssh_command",
        help='SSH command copied from the AWS console, e.g. ssh -i "key.pem" ec2-user@host',
    )
    parser.add_argument(
        "--env-path",
        type=Path,
        default=DEFAULT_ENV_PATH,
        help=f"Path to the research_pipeline .env file (default: {DEFAULT_ENV_PATH})",
    )
    parser.add_argument(
        "--git-name",
        default="AE Scientist",
        help="Git user.name to configure on the worker",
    )
    parser.add_argument(
        "--git-email",
        default="ae-scientist@example.com",
        help="Git user.email to configure on the worker",
    )
    args = parser.parse_args()

    try:
        configure_worker(args)
    except subprocess.CalledProcessError as exc:
        sys.exit(exc.returncode)


if __name__ == "__main__":
    main()
