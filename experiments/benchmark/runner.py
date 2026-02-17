"""Benchmark runner for ae-paper-review evaluation."""

import json
import logging
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from ae_paper_review import ReviewProgressEvent, perform_review

from .metrics import compute_metrics
from .models import BenchmarkConfig, BenchmarkResult, PaperReviewResult

logger = logging.getLogger(__name__)


def load_papers_metadata(*, papers_json_path: Path) -> list[dict[str, Any]]:
    """Load paper metadata from papers.json.

    Args:
        papers_json_path: Path to papers.json file

    Returns:
        List of paper metadata dictionaries
    """
    with open(papers_json_path) as f:
        data: dict[str, Any] = json.load(f)
    return list(data["papers"])


def create_progress_callback(
    *,
    paper_idx: int,
    total_papers: int,
    paper_id: str,
) -> Callable[[ReviewProgressEvent], None]:
    """Create a progress callback for a paper review.

    Args:
        paper_idx: Current paper index (1-based)
        total_papers: Total number of papers
        paper_id: Paper ID

    Returns:
        Callback function for review progress
    """

    def callback(event: ReviewProgressEvent) -> None:
        print(
            f"\r[{paper_idx}/{total_papers}] {paper_id}: "
            f"{event.step} - {event.substep} ({event.progress:.0%})",
            end="",
            flush=True,
        )

    return callback


def review_single_paper(
    *,
    paper: dict,
    pdf_base_path: Path,
    config: BenchmarkConfig,
    paper_idx: int,
    total_papers: int,
) -> PaperReviewResult:
    """Run ae-paper-review on a single paper.

    Args:
        paper: Paper metadata dictionary
        pdf_base_path: Base path for PDF files
        config: Benchmark configuration
        paper_idx: Current paper index (1-based)
        total_papers: Total number of papers

    Returns:
        PaperReviewResult with review data
    """
    paper_id = paper["paper_id"]
    pdf_path = pdf_base_path / paper["pdf_path"]
    now = datetime.now()

    # Base result with real data
    base_result = {
        "paper_id": paper_id,
        "conference": paper["conference"],
        "year": paper["year"],
        "sample_category": paper["sample_category"],
        "real_average_score": paper["average_score"],
        "real_decision": paper["decision"],
        "real_presentation_tier": paper["presentation_tier"],
        "model": config.model,
        "reviewed_at": now,
    }

    if not pdf_path.exists():
        logger.warning(f"PDF not found: {pdf_path}")
        return PaperReviewResult(
            **base_result,
            generated_overall=0.0,
            generated_decision="Unknown",
            generated_confidence=0.0,
            generated_originality=0,
            generated_quality=0,
            generated_clarity=0,
            generated_significance=0,
            input_tokens=0,
            output_tokens=0,
            error=f"PDF not found: {pdf_path}",
        )

    try:
        progress_callback = create_progress_callback(
            paper_idx=paper_idx,
            total_papers=total_papers,
            paper_id=paper_id,
        )

        result = perform_review(
            pdf_path=pdf_path,
            model=config.model,
            temperature=config.temperature,
            event_callback=progress_callback,
            num_reflections=config.num_reflections,
            num_fs_examples=config.num_fs_examples,
            num_reviews_ensemble=config.num_reviews_ensemble,
        )

        print()  # Newline after progress

        return PaperReviewResult(
            **base_result,
            generated_overall=result.review.overall,
            generated_decision=result.review.decision,
            generated_confidence=result.review.confidence,
            generated_originality=result.review.originality,
            generated_quality=result.review.quality,
            generated_clarity=result.review.clarity,
            generated_significance=result.review.significance,
            input_tokens=result.token_usage.input_tokens,
            output_tokens=result.token_usage.output_tokens,
            error=None,
        )

    except Exception as e:
        print()  # Newline after progress
        logger.error(f"Review failed for {paper_id}: {e}")
        return PaperReviewResult(
            **base_result,
            generated_overall=0.0,
            generated_decision="Unknown",
            generated_confidence=0.0,
            generated_originality=0,
            generated_quality=0,
            generated_clarity=0,
            generated_significance=0,
            input_tokens=0,
            output_tokens=0,
            error=str(e),
        )


def save_partial_results(
    *,
    result: BenchmarkResult,
    output_path: Path,
) -> None:
    """Save partial benchmark results to file.

    Args:
        result: Benchmark result to save
        output_path: Output file path
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(result.model_dump(mode="json"), f, indent=2, default=str)


def load_partial_results(*, results_path: Path) -> BenchmarkResult:
    """Load partial benchmark results from file.

    Args:
        results_path: Path to partial results file

    Returns:
        BenchmarkResult loaded from file
    """
    with open(results_path) as f:
        data = json.load(f)
    return BenchmarkResult.model_validate(data)


def run_benchmark(
    *,
    config: BenchmarkConfig,
    papers_json_path: Path,
    pdf_base_path: Path,
    output_path: Path,
) -> BenchmarkResult:
    """Run the full benchmark.

    Automatically resumes from the output file if it exists, skipping
    papers that were already successfully reviewed.

    Args:
        config: Benchmark configuration
        papers_json_path: Path to papers.json
        pdf_base_path: Base path for PDF files
        output_path: Path to save results

    Returns:
        BenchmarkResult with all paper results and computed metrics
    """
    started_at = datetime.now()

    # Load papers
    papers = load_papers_metadata(papers_json_path=papers_json_path)
    logger.info(f"Loaded {len(papers)} papers from {papers_json_path}")

    # Auto-resume: check output file for existing results
    completed_paper_ids: set[str] = set()
    paper_results: list[PaperReviewResult] = []

    if output_path.exists():
        try:
            partial = load_partial_results(results_path=output_path)
            # Only skip papers that succeeded (no error)
            completed_paper_ids = {r.paper_id for r in partial.paper_results if r.error is None}
            # Keep only successful results; failed ones will be retried
            paper_results = [r for r in partial.paper_results if r.error is None]
            started_at = partial.started_at
            n_failed = len(partial.paper_results) - len(paper_results)
            logger.info(
                f"Auto-resuming: found {len(partial.paper_results)} existing reviews, "
                f"{len(paper_results)} successful (keeping), {n_failed} failed (will retry)"
            )
        except Exception as e:
            logger.warning(f"Could not load existing results from {output_path}: {e}")

    # Filter papers to process (skip already completed)
    papers_to_process = [p for p in papers if p["paper_id"] not in completed_paper_ids]

    if config.max_papers is not None:
        remaining = config.max_papers - len(completed_paper_ids)
        if remaining <= 0:
            logger.info(
                f"Already completed {len(completed_paper_ids)} papers, "
                f"reached max_papers={config.max_papers}"
            )
            papers_to_process = []
        else:
            papers_to_process = papers_to_process[:remaining]

    logger.info(f"Processing {len(papers_to_process)} new papers")

    # Process each paper
    total_papers = len(papers_to_process)
    for idx, paper in enumerate(papers_to_process, start=1):
        result = review_single_paper(
            paper=paper,
            pdf_base_path=pdf_base_path,
            config=config,
            paper_idx=idx,
            total_papers=total_papers,
        )
        paper_results.append(result)

        # Save partial results after each paper
        partial_result = BenchmarkResult(
            config=config,
            paper_results=paper_results,
            metrics=None,
            started_at=started_at,
            completed_at=None,
            errors=[r.error for r in paper_results if r.error],
        )
        save_partial_results(result=partial_result, output_path=output_path)

    # Compute final metrics
    metrics = compute_metrics(results=paper_results)

    # Create final result
    final_result = BenchmarkResult(
        config=config,
        paper_results=paper_results,
        metrics=metrics,
        started_at=started_at,
        completed_at=datetime.now(),
        errors=[r.error for r in paper_results if r.error],
    )

    # Save final results
    save_partial_results(result=final_result, output_path=output_path)

    return final_result
