#!/usr/bin/env python3
"""Test script to verify perform_review works with all supported models.

Usage:
    python test_all_models.py
    python test_all_models.py --provider anthropic
    python test_all_models.py --model anthropic:claude-sonnet-4-5
    python test_all_models.py --pdf /path/to/custom.pdf
"""

import argparse
import importlib.resources
import logging
import sys
from pathlib import Path

from ae_paper_review import ReviewProgressEvent, perform_review

# Default test PDF from fewshot examples
DEFAULT_PDF = "2_carpe_diem.pdf"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Supported models from server/app/services/*_service.py
ANTHROPIC_MODELS = [
    "claude-opus-4-5",
    "claude-haiku-4-5",
    "claude-sonnet-4-5",
]

OPENAI_MODELS = [
    "gpt-4.1",
    "gpt-4.1-mini",
    "gpt-4.1-nano",
    "gpt-5",
    "gpt-5.1",
    "gpt-5-nano",
    "gpt-5-mini",
    "gpt-5.2",
]

XAI_MODELS = [
    "grok-4-1-fast-reasoning",
    "grok-4-1-fast-non-reasoning",
    "grok-4-fast-reasoning",
    "grok-4-fast-non-reasoning",
    "grok-4-0709",
]

ALL_MODELS = (
    [f"anthropic:{m}" for m in ANTHROPIC_MODELS]
    + [f"openai:{m}" for m in OPENAI_MODELS]
    + [f"xai:{m}" for m in XAI_MODELS]
)


def progress_callback(event: ReviewProgressEvent) -> None:
    """Print progress events."""
    print(f"  [{event.progress:.0%}] {event.step}: {event.substep}")


def test_model(pdf_path: Path, model: str) -> dict:
    """Test a single model and return results."""
    print(f"\n{'='*60}")
    print(f"Testing model: {model}")
    print("=" * 60)

    try:
        result = perform_review(
            pdf_path,
            model=model,
            temperature=1,
            event_callback=progress_callback,
            num_reflections=1, 
            num_fs_examples=1, 
            num_reviews_ensemble=1, 
        )

        print(f"\nResult:")
        print(f"  Decision: {result.review.decision}")
        print(f"  Overall Score: {result.review.overall}")
        print(f"  Confidence: {result.review.confidence}")
        print(f"  Token Usage:")
        print(f"    Input: {result.token_usage.input_tokens}")
        print(f"    Cached: {result.token_usage.cached_input_tokens}")
        print(f"    Output: {result.token_usage.output_tokens}")

        return {
            "model": model,
            "success": True,
            "decision": result.review.decision,
            "overall": result.review.overall,
            "input_tokens": result.token_usage.input_tokens,
            "output_tokens": result.token_usage.output_tokens,
        }

    except Exception as exc:
        print(f"\nFailed: {exc}")
        logger.exception("Model %s failed", model)
        return {
            "model": model,
            "success": False,
            "error": str(exc),
        }


def get_default_pdf_path() -> Path:
    """Get the path to the default test PDF from fewshot examples."""
    files = importlib.resources.files("ae_paper_review.fewshot_examples")
    pdf_file = files.joinpath(DEFAULT_PDF)
    with importlib.resources.as_file(pdf_file) as pdf_path:
        return Path(pdf_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Test perform_review with all supported models")
    parser.add_argument(
        "--pdf",
        type=Path,
        help=f"Path to a PDF file to review (default: fewshot_examples/{DEFAULT_PDF})",
    )
    parser.add_argument(
        "--provider",
        choices=["anthropic", "openai", "xai"],
        help="Only test models from this provider",
    )
    parser.add_argument(
        "--model",
        help="Test a specific model (e.g., 'anthropic:claude-sonnet-4-5')",
    )
    parser.add_argument(
        "--num-reflections",
        type=int,
        default=1,
        help="Number of reflection rounds (default: 1)",
    )
    parser.add_argument(
        "--num-fs-examples",
        type=int,
        default=0,
        help="Number of few-shot examples (default: 0)",
    )
    parser.add_argument(
        "--num-ensemble",
        type=int,
        default=1,
        help="Number of ensemble reviews (default: 1)",
    )
    args = parser.parse_args()

    # Get PDF path
    if args.pdf:
        pdf_path = args.pdf
        if not pdf_path.exists():
            print(f"Error: PDF file not found: {pdf_path}")
            sys.exit(1)
    else:
        pdf_path = get_default_pdf_path()

    # Determine which models to test
    if args.model:
        models_to_test = [args.model]
    elif args.provider:
        if args.provider == "anthropic":
            models_to_test = [f"anthropic:{m}" for m in ANTHROPIC_MODELS]
        elif args.provider == "openai":
            models_to_test = [f"openai:{m}" for m in OPENAI_MODELS]
        elif args.provider == "xai":
            models_to_test = [f"xai:{m}" for m in XAI_MODELS]
    else:
        models_to_test = ALL_MODELS

    print(f"Testing {len(models_to_test)} model(s) with PDF: {pdf_path}")
    print(f"Settings: reflections={args.num_reflections}, fs_examples={args.num_fs_examples}, ensemble={args.num_ensemble}")

    results = []
    for model in models_to_test:
        result = test_model(pdf_path, model)
        results.append(result)

    # Print summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    successful = [r for r in results if r["success"]]
    failed = [r for r in results if not r["success"]]

    print(f"\nSuccessful: {len(successful)}/{len(results)}")
    for r in successful:
        print(f"  {r['model']}: decision={r['decision']}, overall={r['overall']}, tokens={r['input_tokens']}+{r['output_tokens']}")

    if failed:
        print(f"\nFailed: {len(failed)}/{len(results)}")
        for r in failed:
            print(f"  {r['model']}: {r['error']}")

    sys.exit(0 if not failed else 1)


if __name__ == "__main__":
    main()
