"""
GPU discovery and simple process-level allocation utilities.

Notes:
- Avoids importing torch; uses nvidia-smi
- Provides a minimal manager to reserve/release GPUs per process id
"""

import subprocess
from typing import Dict, Set, TypedDict


class GPUManager:
    """Manages GPU allocation across processes."""

    def __init__(self, num_gpus: int):
        self.num_gpus = num_gpus
        self.available_gpus: Set[int] = set(range(num_gpus))
        self.gpu_assignments: Dict[str, int] = {}

    def acquire_gpu(self, process_id: str) -> int:
        """Assign a GPU to a process, returning the GPU id."""
        if not self.available_gpus:
            raise RuntimeError("No GPUs available")
        gpu_id = min(self.available_gpus)
        self.available_gpus.remove(gpu_id)
        self.gpu_assignments[process_id] = gpu_id
        return gpu_id

    def release_gpu(self, process_id: str) -> None:
        """Release a GPU previously assigned to a process."""
        if process_id in self.gpu_assignments:
            gpu_id = self.gpu_assignments[process_id]
            self.available_gpus.add(gpu_id)
            del self.gpu_assignments[process_id]


class GPUSpec(TypedDict):
    name: str
    memory_total_mib: int


def get_gpu_count() -> int:
    """Return number of available NVIDIA GPUs without importing torch."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=gpu_name", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            check=True,
        )
        gpus = result.stdout.strip().split("\n")
        return len(gpus) if gpus != [""] else 0
    except (subprocess.SubprocessError, FileNotFoundError):
        return 0


def get_gpu_specs(gpu_id: int) -> GPUSpec:
    """Return name and total memory (MiB) for the specified GPU id using nvidia-smi."""
    query_fields = [
        "index",
        "name",
        "memory.total",
    ]
    try:
        result = subprocess.run(
            args=[
                "nvidia-smi",
                "-i",
                str(gpu_id),
                f"--query-gpu={','.join(query_fields)}",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.SubprocessError, FileNotFoundError):
        return {"name": "Unknown", "memory_total_mib": 0}

    lines = [line for line in result.stdout.strip().splitlines() if line]
    if not lines:
        return {"name": "Unknown", "memory_total_mib": 0}

    # Expect a single line for the selected GPU id
    parts = [p.strip() for p in lines[0].split(",")]
    if len(parts) != len(query_fields):
        return {"name": "Unknown", "memory_total_mib": 0}
    _, name, mem_total_str = parts
    try:
        mem_total_mib = int(mem_total_str)
    except ValueError:
        return {"name": name or "Unknown", "memory_total_mib": 0}
    return {"name": name, "memory_total_mib": mem_total_mib}
