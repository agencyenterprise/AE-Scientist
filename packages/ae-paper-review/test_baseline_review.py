#!/usr/bin/env python3
"""Test script to verify perform_baseline_review works with GPT-5.2.

Loads OpenAI API key from server/.env and uses a PDF from ./workspaces.

Usage:
    python test_baseline_review.py
    python test_baseline_review.py --pdf /path/to/custom.pdf
    python test_baseline_review.py --conference neurips_2025
"""

import argparse
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from ae_paper_review import (
    Conference,
    Provider,
    ReviewProgressEvent,
    perform_baseline_review,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

PROVIDER = Provider.OPENAI
MODEL = "gpt-5.2"
WORKSPACES_DIR = Path(__file__).resolve().parent.parent.parent / "workspaces" / "2025"
SERVER_ENV = Path(__file__).resolve().parent.parent.parent / "server" / ".env"


def progress_callback(event: ReviewProgressEvent) -> None:
    print(f"  [{event.progress:.0%}] {event.step}: {event.substep}")


def find_pdf(workspaces_dir: Path) -> Path:
    """Pick the first PDF found in workspaces/2025/."""
    pdfs = sorted(workspaces_dir.glob("*.pdf"))
    if not pdfs:
        print(f"Error: No PDF files found in {workspaces_dir}")
        sys.exit(1)
    return pdfs[0]


def run_test(pdf_path: Path, conference: Conference) -> None:
    print(f"\nPDF: {pdf_path}")
    print(f"Model: {PROVIDER.value}:{MODEL}")
    print(f"Conference: {conference.value}")
    print("=" * 60)

    # Match server TIER_CONFIGS[ReviewTier.STANDARD] exactly
    result = perform_baseline_review(
        pdf_path=pdf_path,
        provider=PROVIDER,
        model=MODEL,
        temperature=1,
        event_callback=progress_callback,
        num_reflections=0,
        conference=conference,
        provide_rubric=True,
        skip_novelty_search=False,
        skip_citation_check=False,
        is_vanilla_prompt=True,
    )

    print("\nResult:")
    print(f"  Decision: {result.review.decision}")
    print(f"  Overall Score: {result.review.overall}")
    print(f"  Summary: {result.review.summary[:200]}...")
    print("\n  Token Usage:")
    print(f"    Input: {result.token_usage.input_tokens}")
    print(f"    Cached: {result.token_usage.cached_input_tokens}")
    print(f"    Output: {result.token_usage.output_tokens}")
    print("\nBaseline review completed successfully.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Test perform_baseline_review with GPT-5.2")
    parser.add_argument(
        "--pdf",
        type=Path,
        help="Path to a PDF file to review (default: first PDF in workspaces/2025/)",
    )
    parser.add_argument(
        "--conference",
        choices=[c.value for c in Conference],
        default=Conference.NEURIPS_2025.value,
        help="Conference rubric to use (default: neurips_2025)",
    )
    args = parser.parse_args()

    # Load env from server/.env
    if SERVER_ENV.exists():
        load_dotenv(dotenv_path=SERVER_ENV)
        print(f"Loaded env from {SERVER_ENV}")
    else:
        print(f"Warning: {SERVER_ENV} not found, relying on environment variables")

    if not os.environ.get("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY not set")
        sys.exit(1)

    pdf_path = args.pdf if args.pdf is not None else find_pdf(WORKSPACES_DIR)
    if not pdf_path.exists():
        print(f"Error: PDF file not found: {pdf_path}")
        sys.exit(1)

    conference = Conference(args.conference)

    run_test(pdf_path=pdf_path, conference=conference)


if __name__ == "__main__":
    main()
