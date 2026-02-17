"""CLI for running ae-paper-review benchmark."""

import argparse
import logging
import sys
from pathlib import Path

from .models import BenchmarkConfig
from .runner import run_benchmark

logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run ae-paper-review benchmark against OpenReview scores."
    )
    parser.add_argument(
        "--papers-json",
        type=Path,
        default=Path("./data/papers.json"),
        help="Path to papers.json metadata file (default: ./data/papers.json)",
    )
    parser.add_argument(
        "--pdf-base-path",
        type=Path,
        default=Path("./data"),
        help="Base path for PDF files (default: ./data)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("./data/benchmark_results.json"),
        help="Output path for results (default: ./data/benchmark_results.json)",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="anthropic:claude-sonnet-4-5",
        help="Model to use for reviews (default: anthropic:claude-sonnet-4-5)",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=1,
        help="Sampling temperature (default: 1)",
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
        default=1,
        help="Number of few-shot examples (default: 1)",
    )
    parser.add_argument(
        "--num-ensemble",
        type=int,
        default=1,
        help="Number of ensemble reviews (default: 1)",
    )
    parser.add_argument(
        "--max-papers",
        type=int,
        default=None,
        help="Maximum papers to process (default: all)",
    )
    parser.add_argument(
        "--fresh",
        action="store_true",
        help="Start fresh, ignoring any existing results in the output file",
    )
    return parser.parse_args()


def print_metrics_summary(*, result: dict) -> None:
    """Print a summary of benchmark metrics."""
    metrics = result.get("metrics")
    if not metrics:
        print("\nNo metrics computed (no successful reviews)")
        return

    print("\n" + "=" * 60)
    print("BENCHMARK RESULTS SUMMARY")
    print("=" * 60)

    print("\n--- Sample Sizes ---")
    print(f"Total papers evaluated: {metrics['n_total']}")
    print(f"  Random subset: {metrics['n_random']}")
    print(f"  Top-tier subset: {metrics['n_top_tier']}")
    print(f"  Accepted papers: {metrics['n_accepted']}")
    print(f"  Rejected papers: {metrics['n_rejected']}")

    print("\n--- Spearman's ρ (Score Correlation) ---")
    ci_full = metrics.get("spearman_ci_full")
    ci_random = metrics.get("spearman_ci_random_only")

    rho_full = metrics["spearman_rho_full"]
    p_full = metrics["spearman_pvalue_full"]
    if ci_full:
        print(f"Full dataset: ρ = {rho_full:.3f} (p = {p_full:.4f}) 95% CI [{ci_full['lower']:.3f}, {ci_full['upper']:.3f}]")
    else:
        print(f"Full dataset: ρ = {rho_full:.3f} (p = {p_full:.4f})")

    rho_random = metrics["spearman_rho_random_only"]
    p_random = metrics["spearman_pvalue_random_only"]
    if ci_random:
        print(f"Random-only:  ρ = {rho_random:.3f} (p = {p_random:.4f}) 95% CI [{ci_random['lower']:.3f}, {ci_random['upper']:.3f}]")
    else:
        print(f"Random-only:  ρ = {rho_random:.3f} (p = {p_random:.4f})")

    # Sanity check comparison
    rho_diff = abs(metrics["spearman_rho_full"] - metrics["spearman_rho_random_only"])
    if rho_diff > 0.1:
        print(f"  ⚠️  Large difference ({rho_diff:.3f}) suggests top-tier sampling bias")
    else:
        print(f"  ✓  Consistent (difference: {rho_diff:.3f})")

    print("\n--- Classification Metrics (Accept/Reject) ---")
    print(f"AUC-ROC: {metrics['auc_roc']:.3f}")
    print(f"Accuracy: {metrics['accuracy']:.1%}")
    print(f"Precision: {metrics['precision']:.3f}")
    print(f"Recall: {metrics['recall']:.3f}")
    print(f"F1 Score: {metrics['f1_score']:.3f}")

    print("\n--- Confusion Matrix ---")
    tp, tn, fp, fn = (
        metrics["true_positives"],
        metrics["true_negatives"],
        metrics["false_positives"],
        metrics["false_negatives"],
    )
    print("                  Predicted")
    print("                Accept  Reject")
    print(f"Actual Accept    {tp:5d}   {fn:5d}")
    print(f"       Reject    {fp:5d}   {tn:5d}")

    print("\n--- Effect Size ---")
    print(f"Cohen's d: {metrics['cohens_d']:.3f}")
    d = metrics["cohens_d"]
    if abs(d) < 0.2:
        effect = "negligible"
    elif abs(d) < 0.5:
        effect = "small"
    elif abs(d) < 0.8:
        effect = "medium"
    else:
        effect = "large"
    print(f"  Interpretation: {effect} effect")

    print("\n--- Inter-rater Agreement ---")
    kappa = metrics.get("cohens_kappa", 0.0)
    print(f"Cohen's κ: {kappa:.3f}")
    if kappa < 0:
        agreement = "poor"
    elif kappa < 0.20:
        agreement = "slight"
    elif kappa < 0.40:
        agreement = "fair"
    elif kappa < 0.60:
        agreement = "moderate"
    elif kappa < 0.80:
        agreement = "substantial"
    else:
        agreement = "almost perfect"
    print(f"  Interpretation: {agreement} agreement")

    # Per-conference breakdown
    per_conf = metrics.get("per_conference_metrics", [])
    if per_conf:
        print("\n--- Per-Conference Spearman's ρ ---")
        for conf in per_conf:
            rho = conf["spearman_rho"]
            p = conf["spearman_pvalue"]
            n = conf["n_papers"]
            sig = "*" if p < 0.05 else ""
            print(f"  {conf['conference']}: ρ = {rho:.3f} (p = {p:.4f}){sig} (n={n})")

    print("=" * 60)


def main() -> None:
    args = parse_args()

    # Handle --fresh: remove existing output file to start over
    if args.fresh and args.output.exists():
        logger.info(f"--fresh specified, removing existing results: {args.output}")
        args.output.unlink()

    # Build config
    config = BenchmarkConfig(
        model=args.model,
        temperature=args.temperature,
        num_reflections=args.num_reflections,
        num_fs_examples=args.num_fs_examples,
        num_reviews_ensemble=args.num_ensemble,
        max_papers=args.max_papers,
    )

    logger.info(f"Starting benchmark with model: {config.model}")
    logger.info(f"Configuration: {config}")
    logger.info(f"Output: {args.output} (auto-resumes if exists)")

    # Run benchmark
    result = run_benchmark(
        config=config,
        papers_json_path=args.papers_json,
        pdf_base_path=args.pdf_base_path,
        output_path=args.output,
    )

    # Print summary
    result_dict = result.model_dump(mode="json")
    print_metrics_summary(result=result_dict)

    # Print token usage summary
    successful_results = [r for r in result.paper_results if r.error is None]
    total_input = sum(r.input_tokens for r in successful_results)
    total_output = sum(r.output_tokens for r in successful_results)

    print("\n--- Token Usage ---")
    print(f"Total input tokens: {total_input:,}")
    print(f"Total output tokens: {total_output:,}")
    print(f"Total tokens: {total_input + total_output:,}")

    if successful_results:
        avg_input = total_input / len(successful_results)
        avg_output = total_output / len(successful_results)
        print(f"Average per paper: {avg_input:,.0f} input, {avg_output:,.0f} output")

    # Print errors if any
    errors = [r for r in result.paper_results if r.error]
    if errors:
        print(f"\n--- Errors ({len(errors)} papers) ---")
        for r in errors[:5]:
            print(f"  {r.paper_id}: {r.error}")
        if len(errors) > 5:
            print(f"  ... and {len(errors) - 5} more")

    logger.info(f"Results saved to {args.output}")


if __name__ == "__main__":
    main()
