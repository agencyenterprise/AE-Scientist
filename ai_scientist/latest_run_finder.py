from pathlib import Path


def normalize_run_name(run_arg: str) -> str:
    s = run_arg.strip()
    if s.isdigit():
        return f"{s}-run"
    if s.startswith("run-") and s[4:].isdigit():
        return f"{s[4:]}-run"
    return s


def find_latest_run_dir_name(logs_dir: Path) -> str:
    if not logs_dir.exists():
        raise FileNotFoundError(str(logs_dir))
    candidates = [d for d in logs_dir.iterdir() if d.is_dir() and d.name.endswith("-run")]
    if not candidates:
        raise FileNotFoundError(f"No run directories found under {logs_dir}")

    def _run_number(p: Path) -> int:
        try:
            return int(p.name.split("-")[0])
        except Exception:
            return -1

    latest = sorted(candidates, key=_run_number, reverse=True)[0]
    return latest.name
