#!/usr/bin/env python3
"""Database migration utility for AE Scientist"""

import subprocess
import sys


def run_command(command: list[str]) -> int:
    """Run a command and return the exit code."""
    print(f"Running: {' '.join(command)}")
    return subprocess.call(command)


def main() -> None:
    """Main migration utility."""
    if len(sys.argv) < 2:
        print("Usage: python migrate.py <command>")
        print("Commands:")
        print("  upgrade      - Apply all pending migrations")
        print("  current      - Show current migration version")
        print("  history      - Show migration history")
        print("  heads        - Show current head revisions")
        print("  revision     - Create a new migration")
        sys.exit(1)

    command = sys.argv[1]

    if command == "upgrade":
        sys.exit(run_command([sys.executable, "-m", "alembic", "upgrade", "head"]))
    elif command == "current":
        sys.exit(run_command([sys.executable, "-m", "alembic", "current"]))
    elif command == "history":
        sys.exit(run_command([sys.executable, "-m", "alembic", "history", "--verbose"]))
    elif command == "heads":
        sys.exit(run_command([sys.executable, "-m", "alembic", "heads"]))
    elif command == "revision":
        if len(sys.argv) < 3:
            print("Usage: python migrate.py revision <message>")
            sys.exit(1)
        message = " ".join(sys.argv[2:])
        sys.exit(run_command([sys.executable, "-m", "alembic", "revision", "-m", message]))
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
