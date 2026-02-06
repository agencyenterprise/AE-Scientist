"""
RunPod GPU pricing and specs utilities.

This module is intentionally self-contained so the API can fetch GPU prices without
pulling in the rest of the RunPod pod lifecycle logic.
"""

# pylint: disable=import-error,global-statement,broad-exception-caught

import asyncio
import logging
import time
from typing import NamedTuple, Sequence, cast

import runpod  # type: ignore

from app.config import settings

logger = logging.getLogger(__name__)

_GPU_INFO_CACHE_TTL_SECONDS = 15 * 60


class CachedGpuInfo(NamedTuple):
    gpu_type: str
    secure_price: float | None
    display_name: str | None
    memory_in_gb: int | None


class FetchedGpuInfo(NamedTuple):
    gpu_type: str
    secure_price: float | None
    display_name: str | None
    memory_in_gb: int | None


class GpuDisplayInfo(NamedTuple):
    """Display information for a GPU type."""

    gpu_type: str
    display_name: str
    memory_in_gb: int | None


_gpu_info_cache: list[CachedGpuInfo] = []
_gpu_info_cache_updated_at_monotonic: float | None = None

_gpu_info_refresh_task: asyncio.Task[None] | None = None
_gpu_info_refresh_lock = asyncio.Lock()
_gpu_info_refresh_pending_types: set[str] = set()


def _cache_age_seconds(*, now_monotonic: float) -> float | None:
    if _gpu_info_cache_updated_at_monotonic is None:
        return None
    age_seconds = now_monotonic - _gpu_info_cache_updated_at_monotonic
    return age_seconds if age_seconds >= 0 else None


def _is_cache_valid(*, now_monotonic: float) -> bool:
    if _gpu_info_cache_updated_at_monotonic is None:
        return False
    age_seconds = now_monotonic - _gpu_info_cache_updated_at_monotonic
    return age_seconds >= 0 and age_seconds < _GPU_INFO_CACHE_TTL_SECONDS


def _merge_cache(
    *,
    existing: Sequence[CachedGpuInfo],
    updates: Sequence[CachedGpuInfo],
) -> list[CachedGpuInfo]:
    by_type: dict[str, CachedGpuInfo] = {entry.gpu_type: entry for entry in existing}
    for entry in updates:
        by_type[entry.gpu_type] = entry
    return list(by_type.values())


def _cached_gpu_types(*, existing: Sequence[CachedGpuInfo]) -> set[str]:
    return {entry.gpu_type for entry in existing}


def _get_cached_info(*, existing: Sequence[CachedGpuInfo], gpu_type: str) -> CachedGpuInfo | None:
    for entry in existing:
        if entry.gpu_type == gpu_type:
            return entry
    return None


def _update_cache(*, gpu_infos: Sequence[CachedGpuInfo], now_monotonic: float) -> None:
    global _gpu_info_cache
    global _gpu_info_cache_updated_at_monotonic
    _gpu_info_cache = _merge_cache(existing=_gpu_info_cache, updates=gpu_infos)
    _gpu_info_cache_updated_at_monotonic = now_monotonic
    logger.info(
        "Updated RunPod GPU info cache (updated=%s total_cached=%s)",
        len(gpu_infos),
        len(_gpu_info_cache),
    )


async def get_gpu_type_prices(*, gpu_types: Sequence[str]) -> dict[str, float | None]:
    """
    Return securePrice per GPU type (USD/hour), keyed by the RunPod GPU type id.

    This function never blocks on RunPod calls:
    - If cache is valid, returns cached values.
    - If cache is stale/missing, returns cached (stale) values if present, otherwise nulls,
      and schedules a background refresh.
    - If RUNPOD_API_KEY is missing, returns nulls.
    """
    now = time.monotonic()
    requested = [gpu_type for gpu_type in gpu_types if gpu_type]

    cache_is_fresh = _is_cache_valid(now_monotonic=now)
    age_seconds = _cache_age_seconds(now_monotonic=now)

    # Always return cached values when available, even if cache is stale.
    cached_types = _cached_gpu_types(existing=_gpu_info_cache)
    any_cached = any(gpu_type in cached_types for gpu_type in requested)
    prices_to_return: dict[str, float | None]
    if any_cached:
        prices_to_return = {}
        for gpu_type in requested:
            info = _get_cached_info(existing=_gpu_info_cache, gpu_type=gpu_type)
            prices_to_return[gpu_type] = info.secure_price if info else None
    else:
        prices_to_return = {gpu_type: None for gpu_type in requested}

    missing_types = [gpu_type for gpu_type in requested if gpu_type not in cached_types]
    should_refresh = (not cache_is_fresh) or bool(missing_types)
    if cache_is_fresh and not missing_types:
        logger.info(
            "RunPod GPU info cache hit (age_s=%s ttl_s=%s requested=%s)",
            age_seconds,
            _GPU_INFO_CACHE_TTL_SECONDS,
            len(requested),
        )
        return prices_to_return

    logger.info(
        "RunPod GPU info cache stale/miss (age_s=%s ttl_s=%s requested=%s missing=%s); returning cached and refreshing",
        age_seconds,
        _GPU_INFO_CACHE_TTL_SECONDS,
        len(requested),
        len(missing_types),
    )
    if should_refresh:
        await _ensure_refresh_scheduled(gpu_types=requested)
    return prices_to_return


async def get_gpu_display_info(*, gpu_types: Sequence[str]) -> dict[str, GpuDisplayInfo]:
    """
    Return display information (name with VRAM) per GPU type.

    This function never blocks on RunPod calls:
    - If cache is valid, returns cached values.
    - If cache is stale/missing, returns cached (stale) values if present,
      and schedules a background refresh.
    """
    now = time.monotonic()
    requested = [gpu_type for gpu_type in gpu_types if gpu_type]

    cache_is_fresh = _is_cache_valid(now_monotonic=now)
    cached_types = _cached_gpu_types(existing=_gpu_info_cache)

    display_info: dict[str, GpuDisplayInfo] = {}
    for gpu_type in requested:
        info = _get_cached_info(existing=_gpu_info_cache, gpu_type=gpu_type)
        if info and info.display_name:
            display_info[gpu_type] = GpuDisplayInfo(
                gpu_type=gpu_type,
                display_name=info.display_name,
                memory_in_gb=info.memory_in_gb,
            )
        else:
            # Fallback to gpu_type as display name
            display_info[gpu_type] = GpuDisplayInfo(
                gpu_type=gpu_type,
                display_name=gpu_type,
                memory_in_gb=None,
            )

    missing_types = [gpu_type for gpu_type in requested if gpu_type not in cached_types]
    should_refresh = (not cache_is_fresh) or bool(missing_types)
    if should_refresh:
        await _ensure_refresh_scheduled(gpu_types=requested)

    return display_info


async def warm_gpu_price_cache(*, gpu_types: Sequence[str]) -> None:
    """
    Schedule a background refresh for the given GPU types.

    Intended for server startup so user-facing endpoints likely have cached prices ready.
    """
    requested = [gpu_type for gpu_type in gpu_types if gpu_type]
    if not requested:
        return
    await _ensure_refresh_scheduled(gpu_types=requested)


async def _ensure_refresh_scheduled(*, gpu_types: Sequence[str]) -> None:
    global _gpu_info_refresh_task
    async with _gpu_info_refresh_lock:
        _gpu_info_refresh_pending_types.update(gpu_types)
        if _gpu_info_refresh_task is not None and not _gpu_info_refresh_task.done():
            logger.info(
                "RunPod GPU info refresh already in progress; queued additional GPU types (queued=%s)",
                len(_gpu_info_refresh_pending_types),
            )
            return
        logger.info(
            "Scheduling RunPod GPU info refresh (queued=%s)",
            len(_gpu_info_refresh_pending_types),
        )
        _gpu_info_refresh_task = asyncio.create_task(_refresh_cache())


async def _refresh_cache() -> None:
    global _gpu_info_refresh_task
    while True:
        async with _gpu_info_refresh_lock:
            pending = sorted(_gpu_info_refresh_pending_types)
            _gpu_info_refresh_pending_types.clear()
        if not pending:
            return

        started_monotonic = time.monotonic()
        try:
            fetched = await _fetch_gpu_info(gpu_types=pending)
            cache_updates = [
                CachedGpuInfo(
                    gpu_type=item.gpu_type,
                    secure_price=item.secure_price,
                    display_name=item.display_name,
                    memory_in_gb=item.memory_in_gb,
                )
                for item in fetched
            ]
            _update_cache(gpu_infos=cache_updates, now_monotonic=time.monotonic())
            duration_seconds = max(0.0, time.monotonic() - started_monotonic)
            missing_count = sum(1 for item in fetched if item.secure_price is None)
            logger.info(
                "RunPod GPU info refresh complete (requested=%s missing=%s duration_s=%.2f)",
                len(pending),
                missing_count,
                duration_seconds,
            )
            for item in fetched:
                logger.info(
                    "RunPod get_gpu summary gpu_type=%s secure_price=%s display_name=%s memory_gb=%s",
                    item.gpu_type,
                    item.secure_price,
                    item.display_name,
                    item.memory_in_gb,
                )
        except Exception:  # noqa: BLE001
            logger.exception("RunPod GPU info refresh failed (requested=%s)", len(pending))
        finally:
            async with _gpu_info_refresh_lock:
                if _gpu_info_refresh_task is not None and _gpu_info_refresh_task.done():
                    _gpu_info_refresh_task = None


async def _fetch_gpu_info(*, gpu_types: Sequence[str]) -> list[FetchedGpuInfo]:
    def _fetch_one_sync(gpu_type: str) -> FetchedGpuInfo:
        gpu_info = runpod.get_gpu(gpu_type)
        if not isinstance(gpu_info, dict):
            return FetchedGpuInfo(
                gpu_type=gpu_type,
                secure_price=None,
                display_name=None,
                memory_in_gb=None,
            )

        # Extract secure price
        secure_price: float | None = None
        secure_price_raw = gpu_info.get("securePrice")
        if secure_price_raw is not None:
            try:
                secure_price = float(secure_price_raw)
            except (TypeError, ValueError):
                pass

        # Extract display name
        display_name = gpu_info.get("displayName")
        if display_name is not None:
            display_name = str(display_name)

        # Extract memory in GB
        memory_in_gb: int | None = None
        memory_raw = gpu_info.get("memoryInGb")
        if memory_raw is not None:
            try:
                memory_in_gb = int(memory_raw)
            except (TypeError, ValueError):
                pass

        return FetchedGpuInfo(
            gpu_type=gpu_type,
            secure_price=secure_price,
            display_name=display_name,
            memory_in_gb=memory_in_gb,
        )

    runpod.api_key = settings.runpod.api_key
    tasks = [asyncio.to_thread(_fetch_one_sync, gpu_type) for gpu_type in gpu_types]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    fetched: list[FetchedGpuInfo] = []
    for result in results:
        if isinstance(result, BaseException):
            logger.exception("RunPod get_gpu call failed during parallel refresh", exc_info=result)
            continue
        fetched.append(cast(FetchedGpuInfo, result))

    fetched_types = {item.gpu_type for item in fetched}
    for gpu_type in gpu_types:
        if gpu_type in fetched_types:
            continue
        fetched.append(
            FetchedGpuInfo(
                gpu_type=gpu_type,
                secure_price=None,
                display_name=None,
                memory_in_gb=None,
            )
        )

    return fetched
