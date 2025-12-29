import logging
import os

import sentry_sdk
from sentry_sdk import configure_scope

_logger = logging.getLogger(__name__)
_SENTRY_INITIALIZED = False


def init_sentry() -> None:
    global _SENTRY_INITIALIZED
    if _SENTRY_INITIALIZED:
        return
    dsn = os.environ.get("SENTRY_DSN", "").strip()
    if not dsn:
        return
    environment_value = (
        os.environ.get("SENTRY_ENVIRONMENT", "").strip()
        or os.environ.get("RAILWAY_ENVIRONMENT_NAME", "").strip()
    )
    try:
        sentry_sdk.init(
            dsn=dsn,
            environment=environment_value or None,
            traces_sample_rate=1.0,
            send_default_pii=True,
        )
    except Exception:  # noqa: BLE001
        _logger.exception("Failed to initialize Sentry for research pipeline.")
        return
    _SENTRY_INITIALIZED = True


def set_sentry_run_context(*, run_id: str) -> None:
    if not run_id or not _SENTRY_INITIALIZED:
        return
    try:
        with configure_scope() as scope:
            scope.set_tag("run_id", run_id)
    except Exception:  # noqa: BLE001
        _logger.exception("Failed to set Sentry run context.")
