#!/usr/bin/env python3
"""Test script to verify perform_review works with all supported models.

Usage:
    python test_all_models.py
    python test_all_models.py --provider anthropic
    python test_all_models.py --model anthropic:claude-sonnet-4-5
    python test_all_models.py --pdf /path/to/custom.pdf
"""

import argparse
import logging
import sys
from pathlib import Path

from ae_paper_review import Conference, Provider, ReviewProgressEvent, perform_review

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Supported models from server/app/services/*_service.py
ANTHROPIC_MODELS = [
    "claude-opus-4-6",
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
        provider_str, model_name = model.split(":", 1)
        result = perform_review(
            pdf_path=pdf_path,
            provider=Provider(provider_str),
            model=model_name,
            temperature=1.0,
            event_callback=progress_callback,
            num_reflections=1,
            conference=Conference.NEURIPS_2025,
            provide_rubric=True,
            skip_novelty_search=False,
            skip_citation_check=False,
            skip_missing_references=False,
            skip_presentation_check=False,
            is_vanilla_prompt=False,
        )

        print("\nResult:")
        print(f"  Decision: {result.review.decision}")
        print(f"  Overall Score: {result.review.overall}")
        print(f"  Confidence: {result.review.confidence}")
        print("  Token Usage:")
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Test perform_review with all supported models")
    parser.add_argument(
        "--pdf",
        type=Path,
        help="Path to a PDF file to review",
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
    args = parser.parse_args()

    # Get PDF path
    if args.pdf is None:
        print("Error: --pdf is required because no default sample PDF is bundled.")
        sys.exit(1)

    pdf_path = args.pdf
    if not pdf_path.exists():
        print(f"Error: PDF file not found: {pdf_path}")
        sys.exit(1)

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
