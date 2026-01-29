"""Multipart parallel download manager for large files."""

import logging
import math
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable

import humanize
import requests
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger("ai-scientist")

# Threshold for using multipart download (100 MB)
MULTIPART_THRESHOLD_BYTES = 100 * 1024 * 1024

# Part size for multipart download (50 MB)
MULTIPART_PART_SIZE_BYTES = 50 * 1024 * 1024

# Maximum concurrent download workers
MAX_DOWNLOAD_WORKERS = 4

# Timeout for individual part downloads (10 minutes)
PART_DOWNLOAD_TIMEOUT_SECONDS = 600


class MultipartDownloader:
    """Downloads files using parallel multipart requests for large files."""

    def __init__(
        self,
        *,
        progress_callback: Callable[[str], None] | None = None,
        max_workers: int = MAX_DOWNLOAD_WORKERS,
    ) -> None:
        """Initialize the downloader.

        Args:
            progress_callback: Optional callback for progress messages.
            max_workers: Maximum number of parallel download workers.
        """
        self._progress_callback = progress_callback or (lambda _: None)
        self._max_workers = max_workers

    def _log_progress(self, message: str) -> None:
        """Log progress message and call callback."""
        logger.info(message)
        print(message, flush=True)
        self._progress_callback(message)

    def download(
        self,
        *,
        url: str,
        file_size: int,
        output_path: Path,
    ) -> None:
        """Download a file, using multipart for large files.

        Args:
            url: Presigned download URL.
            file_size: Size of the file in bytes.
            output_path: Path to save the downloaded file.
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if file_size > MULTIPART_THRESHOLD_BYTES:
            self._download_multipart(url=url, file_size=file_size, output_path=output_path)
        else:
            self._download_streaming(url=url, output_path=output_path)

    def _download_streaming(self, *, url: str, output_path: Path) -> None:
        """Download file using simple streaming (for smaller files)."""
        self._log_progress(f"[download] Downloading {output_path.name} via streaming...")

        response = self._request_streaming(url=url)
        bytes_written = 0

        with open(output_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
                bytes_written += len(chunk)

        self._log_progress(
            f"[download] Completed: {output_path.name} ({humanize.naturalsize(bytes_written, binary=True)})"
        )

    @retry(
        retry=retry_if_exception_type((requests.RequestException, OSError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, max=30),
        reraise=True,
    )
    def _request_streaming(self, *, url: str) -> requests.Response:
        """Make streaming GET request with retry logic."""
        response = requests.get(url, timeout=3600, stream=True)
        response.raise_for_status()
        return response

    def _download_multipart(
        self,
        *,
        url: str,
        file_size: int,
        output_path: Path,
    ) -> None:
        """Download file using parallel multipart requests."""
        num_parts = math.ceil(file_size / MULTIPART_PART_SIZE_BYTES)

        self._log_progress(
            f"[download] Starting multipart download: {output_path.name} "
            f"({humanize.naturalsize(file_size, binary=True)}, {num_parts} parts)"
        )

        # Pre-allocate the output file
        with open(output_path, "wb") as f:
            f.truncate(file_size)

        # Calculate part boundaries
        parts: list[tuple[int, int, int]] = []  # (part_num, start, end)
        for part_num in range(1, num_parts + 1):
            start = (part_num - 1) * MULTIPART_PART_SIZE_BYTES
            # HTTP Range is inclusive, so end is last byte index
            end = min(start + MULTIPART_PART_SIZE_BYTES - 1, file_size - 1)
            parts.append((part_num, start, end))

        # Download parts in parallel
        completed_parts = 0
        total_bytes = 0
        failed_parts: list[int] = []

        with ThreadPoolExecutor(max_workers=self._max_workers) as executor:
            futures = {
                executor.submit(
                    self._download_part,
                    url=url,
                    start=start,
                    end=end,
                    output_path=output_path,
                    part_num=part_num,
                ): part_num
                for part_num, start, end in parts
            }

            for future in as_completed(futures):
                part_num = futures[future]
                try:
                    bytes_written = future.result()
                    total_bytes += bytes_written
                    completed_parts += 1
                    progress_pct = int(completed_parts / num_parts * 100)
                    self._log_progress(
                        f"[download] Part {completed_parts}/{num_parts} complete ({progress_pct}%)"
                    )
                except Exception as e:
                    failed_parts.append(part_num)
                    logger.exception(f"Failed to download part {part_num}: {e}")

        if failed_parts:
            # Clean up partial file
            try:
                output_path.unlink(missing_ok=True)
            except OSError:
                pass
            raise RuntimeError(f"Failed to download parts: {failed_parts}")

        self._log_progress(
            f"[download] Multipart download completed: {output_path.name} ({humanize.naturalsize(total_bytes, binary=True)})"
        )

    @retry(
        retry=retry_if_exception_type((requests.RequestException, OSError)),
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=2, max=60),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    def _download_part(
        self,
        *,
        url: str,
        start: int,
        end: int,
        output_path: Path,
        part_num: int,
    ) -> int:
        """Download a single part (byte range) and write to file.

        Args:
            url: Presigned download URL.
            start: Start byte (inclusive).
            end: End byte (inclusive).
            output_path: Path to output file.
            part_num: Part number (for logging).

        Returns:
            Number of bytes written.
        """
        headers = {"Range": f"bytes={start}-{end}"}
        expected_size = end - start + 1

        response = requests.get(
            url,
            headers=headers,
            timeout=PART_DOWNLOAD_TIMEOUT_SECONDS,
            stream=True,
        )
        response.raise_for_status()

        bytes_written = 0
        with open(output_path, "r+b") as f:
            f.seek(start)
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
                bytes_written += len(chunk)

        if bytes_written != expected_size:
            raise ValueError(
                f"Part {part_num}: expected {expected_size} bytes, got {bytes_written}"
            )

        return bytes_written


def download_file(
    *,
    url: str,
    file_size: int,
    output_path: Path,
    progress_callback: Callable[[str], None] | None = None,
) -> None:
    """Convenience function to download a file with multipart support.

    Args:
        url: Presigned download URL.
        file_size: Size of the file in bytes.
        output_path: Path to save the downloaded file.
        progress_callback: Optional callback for progress messages.
    """
    downloader = MultipartDownloader(progress_callback=progress_callback)
    downloader.download(url=url, file_size=file_size, output_path=output_path)
