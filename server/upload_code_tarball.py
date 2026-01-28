#!/usr/bin/env python
"""
Upload the research_pipeline code tarball to S3.

Run this script once during deployment, before starting uvicorn workers.
This ensures the tarball is uploaded exactly once, avoiding race conditions
when multiple workers try to upload simultaneously.

Usage:
    python upload_code_tarball.py
"""

import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


def main() -> int:
    try:
        from app.services.research_pipeline.runpod.code_packager import ensure_code_tarball_uploaded

        logger.info("Uploading research_pipeline code tarball to S3...")
        s3_key = ensure_code_tarball_uploaded()
        logger.info("Code tarball ready at S3 key: %s", s3_key)
        return 0
    except Exception as e:
        logger.error("Failed to upload code tarball: %s", e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
