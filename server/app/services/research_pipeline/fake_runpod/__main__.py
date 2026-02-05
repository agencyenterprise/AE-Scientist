"""CLI entry point for the fake RunPod server."""

import argparse
import asyncio
import logging
import os
import signal
import sys

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


async def _run_server(host: str, port: int) -> None:
    """Run the server with graceful shutdown handling."""
    config = uvicorn.Config(
        app,
        host=host,
        port=port,
        log_level="debug",
    )
    server = uvicorn.Server(config)

    # Handle shutdown signals gracefully
    loop = asyncio.get_event_loop()
    shutdown_event = asyncio.Event()

    def handle_signal() -> None:
        shutdown_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, handle_signal)

    # Run server until shutdown signal
    serve_task = asyncio.create_task(server.serve())

    await shutdown_event.wait()
    server.should_exit = True
    await serve_task


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
    try:
        asyncio.run(_run_server("127.0.0.1", int(port_value)))
    except KeyboardInterrupt:
        pass
    sys.exit(0)


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    main()
