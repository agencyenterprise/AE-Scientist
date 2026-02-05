"""CLI entry point for the fake RunPod server."""

import argparse
import logging
import os

import uvicorn

from .server import app
from .state import set_speed_factor

logger = logging.getLogger(__name__)


def _require_env(name: str) -> str:
    """Require an environment variable to be set."""
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"{name} is required for fake RunPod server")
    return value


def main() -> None:
    """Run the fake RunPod server."""
    parser = argparse.ArgumentParser(description="Fake RunPod server for local testing")
    parser.add_argument(
        "--speed",
        type=float,
        default=1.0,
        help="Speed multiplier for all wait times (e.g., --speed 2 runs 2x faster)",
    )
    args = parser.parse_args()

    if args.speed <= 0:
        parser.error("--speed must be a positive number")

    set_speed_factor(args.speed)
    if args.speed != 1.0:
        logger.info(
            "Running with speed factor %.1fx (wait times reduced to %.0f%%)",
            args.speed,
            100 / args.speed,
        )

    port_value = _require_env("FAKE_RUNPOD_PORT")
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=int(port_value),
        log_level="debug",
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    main()
