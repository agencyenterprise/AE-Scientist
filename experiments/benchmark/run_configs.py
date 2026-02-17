#!/usr/bin/env python3
"""Run multiple benchmark configurations for comparison.

All configs use: 3 ensemble reviews, 1 reflection (matching production settings).

Models to test:
1. Grok 4.1 Fast Reasoning
2. Grok 4.1 Fast Non-Reasoning
3. GPT-5.2
4. Claude Opus 4.6
"""

import argparse
import json
import logging
import sys
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from benchmark.models import BenchmarkConfig
from benchmark.runner import run_benchmark

logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)


@dataclass
class TestConfig:
    """A benchmark configuration to test."""

    name: str
    model: str
    num_reflections: int
    description: str


# The 5 configurations to test
# All use: 3 ensemble reviews
# num_reflections: 0 = no reflection, 1 = one reflection round
TEST_CONFIGS = [
    TestConfig(
        name="grok-reasoning",
        model="xai:grok-4-1-fast-reasoning",
        num_reflections=0,
        description="Grok 4.1 Fast Reasoning, 3 reviews, no reflection",
    ),
    TestConfig(
        name="grok-non-reasoning",
        model="xai:grok-4-1-fast-non-reasoning",
        num_reflections=0,
        description="Grok 4.1 Fast Non-Reasoning, 3 reviews, no reflection",
    ),
    TestConfig(
        name="gpt-5.2",
        model="openai:gpt-5.2",
        num_reflections=0,
        description="GPT-5.2, 3 reviews, no reflection",
    ),
    TestConfig(
        name="gpt-5.2-reflection",
        model="openai:gpt-5.2",
        num_reflections=1,
        description="GPT-5.2, 3 reviews, 1 reflection",
    ),
    TestConfig(
        name="claude-opus",
        model="anthropic:claude-opus-4-6",
        num_reflections=0,
        description="Claude Opus 4.6, 3 reviews, no reflection",
    ),
]


def run_all_configs(
    *,
    papers_json_path: Path,
    pdf_base_path: Path,
    output_dir: Path,
    max_papers: int | None,
    configs: list[TestConfig],
) -> dict[str, dict]:
    """Run all test configurations.

    Args:
        papers_json_path: Path to papers.json
        pdf_base_path: Base path for PDFs
        output_dir: Directory for output files
        max_papers: Max papers per config (None for all)
        configs: List of test configs to run

    Returns:
        Dict mapping config name to results summary
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    results_summary = {}

    for test_config in configs:
        logger.info(f"\n{'='*60}")
        logger.info(f"Running config: {test_config.name}")
        logger.info(f"  Model: {test_config.model}")
        logger.info(f"  Reflections: {test_config.num_reflections}")
        logger.info(f"={'='*60}")

        config = BenchmarkConfig(
            model=test_config.model,
            temperature=1,
            num_reflections=test_config.num_reflections,
            num_fs_examples=1,
            num_reviews_ensemble=3,
            max_papers=max_papers,
        )

        output_path = output_dir / f"results_{test_config.name}.json"

        try:
            result = run_benchmark(
                config=config,
                papers_json_path=papers_json_path,
                pdf_base_path=pdf_base_path,
                output_path=output_path,
            )

            # Extract key metrics
            metrics = result.metrics
            if metrics:
                summary = {
                    "config": test_config.name,
                    "model": test_config.model,
                    "reflections": test_config.num_reflections,
                    "n_papers": metrics.n_total,
                    "spearman_rho": metrics.spearman_rho_full,
                    "spearman_p": metrics.spearman_pvalue_full,
                    "auc_roc": metrics.auc_roc,
                    "accuracy": metrics.accuracy,
                    "f1_score": metrics.f1_score,
                    "cohens_d": metrics.cohens_d,
                    "total_tokens": sum(
                        r.input_tokens + r.output_tokens
                        for r in result.paper_results
                        if r.error is None
                    ),
                    "errors": len([r for r in result.paper_results if r.error]),
                }
            else:
                summary = {
                    "config": test_config.name,
                    "error": "No metrics computed",
                }

            results_summary[test_config.name] = summary
            logger.info(f"Config {test_config.name} complete: {summary}")

        except Exception as e:
            logger.error(f"Config {test_config.name} failed: {e}")
            results_summary[test_config.name] = {
                "config": test_config.name,
                "error": str(e),
            }

    return results_summary


def print_comparison_table(*, results: dict[str, dict]) -> None:
    """Print a comparison table of all configs."""
    print("\n" + "=" * 80)
    print("CONFIGURATION COMPARISON")
    print("=" * 80)

    # Header
    print(
        f"{'Config':<25} {'Spearman ρ':>12} {'AUC-ROC':>10} {'F1':>8} {'Accuracy':>10} {'Tokens':>12}"
    )
    print("-" * 80)

    # Sort by AUC-ROC descending
    sorted_configs = sorted(
        results.items(),
        key=lambda x: x[1].get("auc_roc", 0),
        reverse=True,
    )

    for name, summary in sorted_configs:
        if "error" in summary and summary.get("n_papers") is None:
            print(f"{name:<25} {'ERROR':>12}")
            continue

        rho = summary.get("spearman_rho", 0)
        auc = summary.get("auc_roc", 0)
        f1 = summary.get("f1_score", 0)
        acc = summary.get("accuracy", 0)
        tokens = summary.get("total_tokens", 0)

        print(f"{name:<25} {rho:>12.3f} {auc:>10.3f} {f1:>8.3f} {acc:>9.1%} {tokens:>12,}")

    print("=" * 80)

    # Recommend best config
    best = sorted_configs[0] if sorted_configs else None
    if best and "error" not in best[1]:
        print(f"\nRecommended config: {best[0]}")
        print(f"  AUC-ROC: {best[1].get('auc_roc', 0):.3f}")
        print(f"  Spearman ρ: {best[1].get('spearman_rho', 0):.3f}")


def main() -> None:
    """Run all benchmark configurations."""
    parser = argparse.ArgumentParser(description="Run multiple benchmark configs")
    parser.add_argument(
        "--papers-json",
        type=Path,
        default=Path("./data_50/papers.json"),
        help="Path to papers.json (default: ./data_50/papers.json)",
    )
    parser.add_argument(
        "--pdf-base-path",
        type=Path,
        default=Path("./data_50"),
        help="Base path for PDFs (default: ./data_50)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("./data_50/benchmark_results"),
        help="Output directory for results (default: ./data_50/benchmark_results)",
    )
    parser.add_argument(
        "--max-papers",
        type=int,
        default=None,
        help="Max papers per config (default: all)",
    )
    parser.add_argument(
        "--config",
        type=str,
        choices=[c.name for c in TEST_CONFIGS],
        help="Run only a specific config",
    )
    args = parser.parse_args()

    # Load .env for API keys
    load_dotenv()

    # Filter to specific config if requested
    configs_to_run = TEST_CONFIGS
    if args.config:
        configs_to_run = [c for c in TEST_CONFIGS if c.name == args.config]

    # Run all configs
    results = run_all_configs(
        papers_json_path=args.papers_json,
        pdf_base_path=args.pdf_base_path,
        output_dir=args.output_dir,
        max_papers=args.max_papers,
        configs=configs_to_run,
    )

    # Save summary
    summary_path = args.output_dir / "comparison_summary.json"
    with open(summary_path, "w") as f:
        json.dump(results, f, indent=2)
    logger.info(f"Summary saved to {summary_path}")

    # Print comparison
    print_comparison_table(results=results)


if __name__ == "__main__":
    main()
