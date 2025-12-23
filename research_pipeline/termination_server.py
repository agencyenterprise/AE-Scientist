"""
Termination web server for handling execution kill requests.
"""

from __future__ import annotations

import asyncio
import logging
import multiprocessing
import multiprocessing.managers
import os
import signal
import threading

import uvicorn
from fastapi import Body, FastAPI, HTTPException
from pydantic import BaseModel

from ai_scientist.treesearch import execution_registry

logger = logging.getLogger(__name__)

_TERMINATION_APP: FastAPI | None = None
_TERMINATION_SERVER: uvicorn.Server | None = None
_TERMINATION_SERVER_THREAD: threading.Thread | None = None
_PID_MANAGER: multiprocessing.managers.SyncManager | None = None


class TerminateRequest(BaseModel):
    payload: str


def initialize_execution_registry() -> None:
    """Ensure the shared execution registry is initialized."""
    global _PID_MANAGER
    if _PID_MANAGER is not None:
        logger.debug("Execution registry manager already initialized; skipping.")
        return
    _PID_MANAGER = multiprocessing.Manager()
    shared_state = _PID_MANAGER.dict()
    execution_registry.setup_shared_pid_state(shared_state)
    logger.info("Execution registry shared PID state initialized (id=%s)", id(shared_state))


def shutdown_execution_registry_manager() -> None:
    """Shutdown the multiprocessing manager backing the execution registry."""
    global _PID_MANAGER
    if _PID_MANAGER is None:
        logger.debug("Execution registry manager already shut down; skipping.")
        return
    _PID_MANAGER.shutdown()
    logger.info("Execution registry shared PID state shut down.")
    _PID_MANAGER = None


def _create_app() -> FastAPI:
    app = FastAPI(title="AE Scientist Termination API")

    @app.post("/terminate/{execution_id}")
    async def terminate_execution(
        execution_id: str,
        request: TerminateRequest = Body(...),
    ) -> dict[str, str]:
        logger.info(
            "Termination server received request for execution_id=%s payload_len=%s",
            execution_id,
            len(request.payload),
        )
        status, pid, _node = execution_registry.begin_termination(
            execution_id=execution_id,
            payload=request.payload,
        )
        if status == "not_found":
            logger.warning(
                "Termination request refused (not found) for execution_id=%s", execution_id
            )
            raise HTTPException(status_code=404, detail="Unknown execution_id")
        if status == "conflict":
            logger.warning("Termination request conflict for execution_id=%s", execution_id)
            raise HTTPException(
                status_code=409,
                detail="Execution already completed or terminating",
            )
        if pid is None:
            execution_registry.clear_execution(execution_id)
            logger.warning(
                "Termination request cannot proceed because PID missing for execution_id=%s",
                execution_id,
            )
            raise HTTPException(status_code=409, detail="Process already exited")

        try:
            logger.info("Sending SIGKILL to pid=%s for execution_id=%s", pid, execution_id)
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError as exc:
            execution_registry.clear_execution(execution_id)
            logger.warning(
                "Process already exited before kill for execution_id=%s (pid=%s)",
                execution_id,
                pid,
            )
            raise HTTPException(status_code=409, detail="Process already exited") from exc
        except PermissionError as exc:
            logger.exception(
                "Failed to signal process pid=%s for execution_id=%s", pid, execution_id
            )
            raise HTTPException(status_code=500, detail="Failed to signal process") from exc

        logger.info("Termination signal delivered for execution_id=%s", execution_id)
        return {"status": "terminating", "execution_id": execution_id}

    @app.get("/healthz")
    async def health_check() -> dict[str, str]:
        logger.debug("Termination server health check requested.")
        return {"status": "ok"}

    return app


def start_termination_server(*, host: str, port: int) -> None:
    """Start the termination FastAPI server in a background thread."""
    global _TERMINATION_APP, _TERMINATION_SERVER, _TERMINATION_SERVER_THREAD
    if _TERMINATION_SERVER_THREAD is not None:
        logger.debug("Termination server already running; skipping start.")
        return
    app = _create_app()
    config = uvicorn.Config(app, host=host, port=port, log_level="info")
    server = uvicorn.Server(config=config)

    def _run_server() -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(server.serve())

    _TERMINATION_APP = app
    _TERMINATION_SERVER = server
    thread = threading.Thread(target=_run_server, name="TerminationServer", daemon=True)
    _TERMINATION_SERVER_THREAD = thread
    thread.start()
    logger.info(
        "Termination server listening on http://%s:%s/terminate/{execution_id}",
        host,
        port,
    )


def stop_termination_server() -> None:
    """Stop the termination server if it is running."""
    global _TERMINATION_SERVER, _TERMINATION_SERVER_THREAD
    if _TERMINATION_SERVER is not None:
        _TERMINATION_SERVER.should_exit = True
    if _TERMINATION_SERVER_THREAD is not None:
        _TERMINATION_SERVER_THREAD.join(timeout=5)
        logger.info("Termination server thread joined.")
    _TERMINATION_SERVER = None
    _TERMINATION_SERVER_THREAD = None
