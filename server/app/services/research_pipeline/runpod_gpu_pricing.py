"""
RunPod GPU pricing utilities.

This module is intentionally self-contained so the API can fetch GPU prices without
pulling in the rest of the RunPod pod lifecycle logic.
"""

# pylint: disable=import-error,global-statement,broad-exception-caught

import asyncio
import logging
import os
import time
from typing import NamedTuple, Sequence, cast

import runpod  # type: ignore
from pydantic import BaseModel

logger = logging.getLogger(__name__)

_GPU_PRICE_CACHE_TTL_SECONDS = 15 * 60


class RunPodGpuInfoSummary(BaseModel):
    id: str | None
    display_name: str | None
    manufacturer: str | None
    memory_gb: int | None
    secure_price: float | None
    community_price: float | None
    secure_spot_price: float | None
    community_spot_price: float | None


class CachedGpuPrice(NamedTuple):
    gpu_type: str
    secure_price: float | None


class FetchedGpuPrice(NamedTuple):
    gpu_type: str
    secure_price: float | None
    summary: RunPodGpuInfoSummary


_gpu_price_cache: list[CachedGpuPrice] = []
_gpu_price_cache_updated_at_monotonic: float | None = None

_gpu_price_refresh_task: asyncio.Task[None] | None = None
_gpu_price_refresh_lock = asyncio.Lock()
_gpu_price_refresh_pending_types: set[str] = set()


def _cache_age_seconds(*, now_monotonic: float) -> float | None:
    if _gpu_price_cache_updated_at_monotonic is None:
        return None
    age_seconds = now_monotonic - _gpu_price_cache_updated_at_monotonic
    return age_seconds if age_seconds >= 0 else None


def _is_cache_valid(*, now_monotonic: float) -> bool:
    if _gpu_price_cache_updated_at_monotonic is None:
        return False
    age_seconds = now_monotonic - _gpu_price_cache_updated_at_monotonic
    return age_seconds >= 0 and age_seconds < _GPU_PRICE_CACHE_TTL_SECONDS


def _merge_cache(
    *,
    existing: Sequence[CachedGpuPrice],
    updates: Sequence[CachedGpuPrice],
) -> list[CachedGpuPrice]:
    by_type: dict[str, float | None] = {entry.gpu_type: entry.secure_price for entry in existing}
    for entry in updates:
        by_type[entry.gpu_type] = entry.secure_price
    return [
        CachedGpuPrice(gpu_type=gpu_type, secure_price=secure_price)
        for gpu_type, secure_price in by_type.items()
    ]


def _cached_gpu_types(*, existing: Sequence[CachedGpuPrice]) -> set[str]:
    return {entry.gpu_type for entry in existing}


def _get_cached_price(*, existing: Sequence[CachedGpuPrice], gpu_type: str) -> float | None:
    for entry in existing:
        if entry.gpu_type == gpu_type:
            return entry.secure_price
    return None


def _update_cache(*, prices: Sequence[CachedGpuPrice], now_monotonic: float) -> None:
    global _gpu_price_cache
    global _gpu_price_cache_updated_at_monotonic
    _gpu_price_cache = _merge_cache(existing=_gpu_price_cache, updates=prices)
    _gpu_price_cache_updated_at_monotonic = now_monotonic
    logger.info(
        "Updated RunPod GPU price cache (updated=%s total_cached=%s)",
        len(prices),
        len(_gpu_price_cache),
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

    runpod_api_key = os.environ.get("RUNPOD_API_KEY")
    if not runpod_api_key:
        logger.info(
            "RUNPOD_API_KEY missing; returning null securePrice for %s GPU types",
            len(requested),
        )
        return {gpu_type: None for gpu_type in requested}

    cache_is_fresh = _is_cache_valid(now_monotonic=now)
    age_seconds = _cache_age_seconds(now_monotonic=now)

    # Always return cached values when available, even if cache is stale.
    cached_types = _cached_gpu_types(existing=_gpu_price_cache)
    any_cached = any(gpu_type in cached_types for gpu_type in requested)
    prices_to_return: dict[str, float | None]
    if any_cached:
        prices_to_return = {
            gpu_type: _get_cached_price(existing=_gpu_price_cache, gpu_type=gpu_type)
            for gpu_type in requested
        }
    else:
        prices_to_return = {gpu_type: None for gpu_type in requested}

    missing_types = [gpu_type for gpu_type in requested if gpu_type not in cached_types]
    should_refresh = (not cache_is_fresh) or bool(missing_types)
    if cache_is_fresh and not missing_types:
        logger.info(
            "RunPod GPU price cache hit (age_s=%s ttl_s=%s requested=%s)",
            age_seconds,
            _GPU_PRICE_CACHE_TTL_SECONDS,
            len(requested),
        )
        return prices_to_return

    logger.info(
        "RunPod GPU price cache stale/miss (age_s=%s ttl_s=%s requested=%s missing=%s); returning cached and refreshing",
        age_seconds,
        _GPU_PRICE_CACHE_TTL_SECONDS,
        len(requested),
        len(missing_types),
    )
    if should_refresh:
        await _ensure_refresh_scheduled(runpod_api_key=runpod_api_key, gpu_types=requested)
    return prices_to_return


async def warm_gpu_price_cache(*, gpu_types: Sequence[str]) -> None:
    """
    Schedule a background refresh for the given GPU types.

    Intended for server startup so user-facing endpoints likely have cached prices ready.
    """
    runpod_api_key = os.environ.get("RUNPOD_API_KEY")
    if not runpod_api_key:
        logger.info("Skipping RunPod GPU price warmup; RUNPOD_API_KEY missing")
        return
    requested = [gpu_type for gpu_type in gpu_types if gpu_type]
    if not requested:
        return
    await _ensure_refresh_scheduled(runpod_api_key=runpod_api_key, gpu_types=requested)


async def _ensure_refresh_scheduled(*, runpod_api_key: str, gpu_types: Sequence[str]) -> None:
    global _gpu_price_refresh_task
    async with _gpu_price_refresh_lock:
        _gpu_price_refresh_pending_types.update(gpu_types)
        if _gpu_price_refresh_task is not None and not _gpu_price_refresh_task.done():
            logger.info(
                "RunPod GPU price refresh already in progress; queued additional GPU types (queued=%s)",
                len(_gpu_price_refresh_pending_types),
            )
            return
        logger.info(
            "Scheduling RunPod GPU price refresh (queued=%s)",
            len(_gpu_price_refresh_pending_types),
        )
        _gpu_price_refresh_task = asyncio.create_task(_refresh_cache(runpod_api_key=runpod_api_key))


async def _refresh_cache(*, runpod_api_key: str) -> None:
    global _gpu_price_refresh_task
    while True:
        async with _gpu_price_refresh_lock:
            pending = sorted(_gpu_price_refresh_pending_types)
            _gpu_price_refresh_pending_types.clear()
        if not pending:
            return

        started_monotonic = time.monotonic()
        try:
            fetched = await _fetch_secure_prices(runpod_api_key=runpod_api_key, gpu_types=pending)
            cache_updates = [
                CachedGpuPrice(gpu_type=item.gpu_type, secure_price=item.secure_price)
                for item in fetched
            ]
            _update_cache(prices=cache_updates, now_monotonic=time.monotonic())
            duration_seconds = max(0.0, time.monotonic() - started_monotonic)
            missing_count = sum(1 for item in fetched if item.secure_price is None)
            logger.info(
                "RunPod GPU price refresh complete (requested=%s missing=%s duration_s=%.2f)",
                len(pending),
                missing_count,
                duration_seconds,
            )
            for item in fetched:
                logger.info(
                    "RunPod get_gpu summary gpu_type=%s summary=%s",
                    item.gpu_type,
                    item.summary.model_dump_json(),
                )
        except Exception:  # noqa: BLE001
            logger.exception("RunPod GPU price refresh failed (requested=%s)", len(pending))
        finally:
            async with _gpu_price_refresh_lock:
                if _gpu_price_refresh_task is not None and _gpu_price_refresh_task.done():
                    _gpu_price_refresh_task = None


async def _fetch_secure_prices(
    *, runpod_api_key: str, gpu_types: Sequence[str]
) -> list[FetchedGpuPrice]:
    def _fetch_one_sync(gpu_type: str) -> FetchedGpuPrice:
        gpu_info = runpod.get_gpu(gpu_type)
        if not isinstance(gpu_info, dict):
            summary = RunPodGpuInfoSummary(
                id=None,
                display_name=None,
                manufacturer=None,
                memory_gb=None,
                secure_price=None,
                community_price=None,
                secure_spot_price=None,
                community_spot_price=None,
            )
            return FetchedGpuPrice(gpu_type=gpu_type, secure_price=None, summary=summary)

        summary = RunPodGpuInfoSummary(
            id=cast(str | None, gpu_info.get("id")),
            display_name=cast(str | None, gpu_info.get("displayName")),
            manufacturer=cast(str | None, gpu_info.get("manufacturer")),
            memory_gb=cast(int | None, gpu_info.get("memoryInGb")),
            secure_price=cast(float | None, gpu_info.get("securePrice")),
            community_price=cast(float | None, gpu_info.get("communityPrice")),
            secure_spot_price=cast(float | None, gpu_info.get("secureSpotPrice")),
            community_spot_price=cast(float | None, gpu_info.get("communitySpotPrice")),
        )

        secure_price_raw = gpu_info.get("securePrice")
        if secure_price_raw is None:
            return FetchedGpuPrice(gpu_type=gpu_type, secure_price=None, summary=summary)
        try:
            return FetchedGpuPrice(
                gpu_type=gpu_type,
                secure_price=float(secure_price_raw),
                summary=summary,
            )
        except (TypeError, ValueError):
            return FetchedGpuPrice(gpu_type=gpu_type, secure_price=None, summary=summary)

    runpod.api_key = runpod_api_key
    tasks = [asyncio.to_thread(_fetch_one_sync, gpu_type) for gpu_type in gpu_types]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    fetched: list[FetchedGpuPrice] = []
    for result in results:
        if isinstance(result, BaseException):
            logger.exception("RunPod get_gpu call failed during parallel refresh", exc_info=result)
            continue
        fetched.append(cast(FetchedGpuPrice, result))

    fetched_types = {item.gpu_type for item in fetched}
    for gpu_type in gpu_types:
        if gpu_type in fetched_types:
            continue
        fetched.append(
            FetchedGpuPrice(
                gpu_type=gpu_type,
                secure_price=None,
                summary=RunPodGpuInfoSummary(
                    id=None,
                    display_name=None,
                    manufacturer=None,
                    memory_gb=None,
                    secure_price=None,
                    community_price=None,
                    secure_spot_price=None,
                    community_spot_price=None,
                ),
            )
        )

    return fetched
