from pathlib import Path


def normalize_run_name(run_arg: str, exp_name: str) -> str:
    s = run_arg.strip()
    suffix = f"-{exp_name}"

    if s.isdigit():
        return f"{s}{suffix}"

    if s.endswith(suffix):
        prefix = s[: -len(suffix)]
        if prefix.isdigit():
            return s

    prefix = f"{exp_name}-"
    if s.startswith(prefix):
        tail = s[len(prefix) :]
        if tail.isdigit():
            return f"{tail}{suffix}"

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
