"""CLI for paper sourcing from OpenReview."""

import argparse
import csv
import json
import logging
import sys
import time
from pathlib import Path

import requests
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from .models import Conference, PaperMetadata, SourcingConfig, SourcingResult
from .sampler import source_all_papers

logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)


@retry(
    retry=retry_if_exception_type(requests.RequestException),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, max=30),
    reraise=True,
)
def download_pdf(*, url: str, output_path: Path, timeout_seconds: int) -> None:
    """Download a PDF file from a URL.

    Args:
        url: URL to download from
        output_path: Local path to save the PDF
        timeout_seconds: Request timeout
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    response = requests.get(
        url,
        timeout=timeout_seconds,
        stream=True,
        headers={"User-Agent": "AE-Scientist-Paper-Sourcing/1.0"},
    )
    response.raise_for_status()

    with open(output_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)


def download_papers(
    *,
    papers: list[PaperMetadata],
    output_dir: Path,
    rate_limit_delay: float,
) -> list[PaperMetadata]:
    """Download PDFs for all papers.

    Args:
        papers: List of papers to download
        output_dir: Root output directory
        rate_limit_delay: Delay between downloads

    Returns:
        Updated list of papers with pdf_path filled in
    """
    updated_papers: list[PaperMetadata] = []

    for i, paper in enumerate(papers):
        relative_path = f"pdfs/{paper.conference.value}/{paper.year}/{paper.paper_id}.pdf"
        output_path = output_dir / relative_path

        if not paper.pdf_url:
            logger.warning(f"No PDF URL for {paper.paper_id}")
            updated_papers.append(paper.model_copy(update={"pdf_path": ""}))
            continue

        if output_path.exists():
            logger.info(f"[{i+1}/{len(papers)}] Already exists: {paper.paper_id}")
            updated_papers.append(paper.model_copy(update={"pdf_path": relative_path}))
            continue

        try:
            time.sleep(rate_limit_delay)
            download_pdf(url=paper.pdf_url, output_path=output_path, timeout_seconds=120)
            logger.info(f"[{i+1}/{len(papers)}] Downloaded: {paper.paper_id}")
            updated_papers.append(paper.model_copy(update={"pdf_path": relative_path}))
        except Exception as e:
            logger.warning(f"[{i+1}/{len(papers)}] Failed {paper.paper_id}: {e}")
            updated_papers.append(paper.model_copy(update={"pdf_path": ""}))

    return updated_papers


def save_papers_json(*, result: SourcingResult, output_path: Path) -> None:
    """Save sourcing result to JSON.

    Args:
        result: Sourcing result
        output_path: Output file path
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(result.model_dump(mode="json"), f, indent=2, default=str)


def save_papers_csv(*, papers: list[PaperMetadata], output_path: Path) -> None:
    """Save papers to CSV for easy analysis.

    Args:
        papers: List of paper metadata
        output_path: Output CSV path
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "paper_id",
                "title",
                "conference",
                "year",
                "average_score",
                "decision",
                "presentation_tier",
                "sample_category",
                "num_reviewers",
                "pdf_path",
                "pdf_url",
            ]
        )

        for paper in papers:
            writer.writerow(
                [
                    paper.paper_id,
                    paper.title,
                    paper.conference.value,
                    paper.year,
                    f"{paper.average_score:.2f}",
                    paper.decision,
                    paper.presentation_tier.value,
                    paper.sample_category.value,
                    len(paper.reviewer_scores),
                    paper.pdf_path,
                    paper.pdf_url,
                ]
            )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Source papers from OpenReview for benchmarking.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("./data"),
        help="Output directory for PDFs and metadata (default: ./data)",
    )
    parser.add_argument(
        "--conferences",
        nargs="+",
        default=["ICLR", "NeurIPS", "ICML"],
        help="Conferences to source from (default: ICLR NeurIPS ICML)",
    )
    parser.add_argument(
        "--years",
        nargs="+",
        type=int,
        default=[2023, 2024],
        help="Years to source (default: 2023 2024)",
    )
    parser.add_argument(
        "--papers-per-conference",
        type=int,
        default=100,
        help="Papers per conference (default: 100)",
    )
    parser.add_argument(
        "--top-tier-per-conference",
        type=int,
        default=15,
        help="Top-tier papers per conference (default: 15)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducibility (default: 42)",
    )
    parser.add_argument(
        "--skip-pdf-download",
        action="store_true",
        help="Skip PDF downloads (metadata only)",
    )
    parser.add_argument(
        "--rate-limit-delay",
        type=float,
        default=1.0,
        help="Delay between PDF downloads in seconds (default: 1.0)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    # Build config
    conferences = [Conference(c) for c in args.conferences]
    config = SourcingConfig(
        conferences=conferences,
        years=args.years,
        papers_per_conference=args.papers_per_conference,
        top_tier_per_conference=args.top_tier_per_conference,
        seed=args.seed,
    )

    logger.info(f"Starting paper sourcing with config: {config}")

    # Source papers
    papers, errors = source_all_papers(config=config)
    logger.info(f"Sourced {len(papers)} papers metadata")

    # Download PDFs if requested
    if not args.skip_pdf_download:
        logger.info("Downloading PDFs...")
        papers = download_papers(
            papers=papers,
            output_dir=args.output_dir,
            rate_limit_delay=args.rate_limit_delay,
        )

    # Create result
    result = SourcingResult(
        config=config,
        papers=papers,
        errors=errors,
    )

    # Save outputs
    json_path = args.output_dir / "papers.json"
    csv_path = args.output_dir / "papers.csv"

    save_papers_json(result=result, output_path=json_path)
    save_papers_csv(papers=papers, output_path=csv_path)

    logger.info(f"Saved {len(papers)} papers to {json_path} and {csv_path}")
    if errors:
        logger.warning(f"Encountered {len(errors)} errors: {errors}")

    # Print summary
    print("\nSourcing complete:")
    print(f"  Total papers: {len(papers)}")
    for conf in conferences:
        conf_papers = [p for p in papers if p.conference == conf]
        random_count = sum(1 for p in conf_papers if p.sample_category.value == "random")
        top_tier_count = sum(1 for p in conf_papers if p.sample_category.value == "top_tier")
        print(
            f"  {conf.value}: {len(conf_papers)} ({random_count} random, {top_tier_count} top-tier)"
        )
    print("\nOutput:")
    print(f"  Metadata: {json_path}")
    print(f"  CSV: {csv_path}")
    if not args.skip_pdf_download:
        print(f"  PDFs: {args.output_dir / 'pdfs'}")


if __name__ == "__main__":
    main()
