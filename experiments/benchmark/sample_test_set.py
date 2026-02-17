"""Sample a test set with specific accept/reject ratios for benchmark testing."""

import logging
import random
import sys
from datetime import datetime
from pathlib import Path

from paper_sourcing.cli import download_papers, save_papers_csv, save_papers_json
from paper_sourcing.models import (
    Conference,
    PaperMetadata,
    PresentationTier,
    SampleCategory,
    SourcingConfig,
    SourcingResult,
)
from paper_sourcing.openreview_client import (
    VenueConfig,
    extract_decision,
    fetch_submissions,
    get_pdf_url,
    get_venue_config,
)
from paper_sourcing.sampler import _note_to_metadata

# Type alias for sampled paper tuples: (note, venue_config, year)
SampledPaper = tuple[object, VenueConfig, int]

logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)


def sample_with_reject_ratio(
    *,
    conference: Conference,
    years: list[int],
    n_accepted: int,
    n_rejected: int,
    seed: int,
) -> list[PaperMetadata]:
    """Sample papers with specific accept/reject counts.

    Args:
        conference: Conference to sample from
        years: Years to sample from
        n_accepted: Number of accepted papers to sample
        n_rejected: Number of rejected papers to sample
        seed: Random seed

    Returns:
        List of sampled PaperMetadata
    """
    # Use deterministic hash (sum of char codes) instead of Python's hash() which is randomized
    conference_offset = sum(ord(c) for c in conference.value)
    rng = random.Random(seed + conference_offset)

    accepted_pool: list[SampledPaper] = []
    rejected_pool: list[SampledPaper] = []

    for year in years:
        venue_config = get_venue_config(conference=conference, year=year)
        if venue_config is None:
            continue

        try:
            submissions = fetch_submissions(config=venue_config)
        except Exception as e:
            logger.warning(f"Failed to fetch {conference.value} {year}: {e}")
            continue

        for note in submissions:
            decision_str, tier = extract_decision(note=note, api_version=venue_config.api_version)

            # Skip unknown decisions
            if tier == PresentationTier.UNKNOWN:
                continue

            # Skip papers without PDFs
            if not get_pdf_url(note=note):
                continue

            item = (note, venue_config, year)
            if tier == PresentationTier.REJECT:
                rejected_pool.append(item)
            else:
                accepted_pool.append(item)

    logger.info(
        f"{conference.value}: {len(accepted_pool)} accepted, "
        f"{len(rejected_pool)} rejected available"
    )

    # Sample
    sampled_accepted = rng.sample(accepted_pool, min(n_accepted, len(accepted_pool)))
    sampled_rejected = rng.sample(rejected_pool, min(n_rejected, len(rejected_pool)))

    logger.info(
        f"Sampled {len(sampled_accepted)} accepted + {len(sampled_rejected)} rejected "
        f"from {conference.value}"
    )

    # Convert to PaperMetadata
    now = datetime.now()
    papers = []

    for note, venue_config, year in sampled_accepted + sampled_rejected:
        paper = _note_to_metadata(
            note=note,
            venue_config=venue_config,
            conference=conference,
            year=year,
            sample_category=SampleCategory.RANDOM,
            sourced_at=now,
        )
        papers.append(paper)

    return papers


def main() -> None:
    """Create 50-paper test set with accept/reject targeting."""
    seed = 42
    output_dir = Path("./data_50")
    years = [2024, 2025]

    # Target: maximize rejected papers given ICML has none
    # ICLR: 25 papers (5 accepted, 20 rejected)
    # NeurIPS: 15 papers (3 accepted, 12 rejected)
    # ICML: 10 papers (10 accepted, 0 rejected)
    # Total: 18 accepted, 32 rejected (36%/64%)

    configs = [
        (Conference.ICLR, 5, 20),  # 25 total
        (Conference.NEURIPS, 3, 12),  # 15 total
        (Conference.ICML, 10, 0),  # 10 total (no rejected available)
    ]

    all_papers: list[PaperMetadata] = []

    for conference, n_accepted, n_rejected in configs:
        papers = sample_with_reject_ratio(
            conference=conference,
            years=years,
            n_accepted=n_accepted,
            n_rejected=n_rejected,
            seed=seed,
        )
        all_papers.extend(papers)

    logger.info(f"Total papers sampled: {len(all_papers)}")

    if not all_papers:
        logger.error("No papers sampled! Check API connectivity and conference availability.")
        return

    # Count final accept/reject
    n_acc = sum(1 for p in all_papers if "reject" not in p.decision.lower())
    n_rej = sum(1 for p in all_papers if "reject" in p.decision.lower())
    reject_pct = n_rej / len(all_papers) * 100
    logger.info(f"Final: {n_acc} accepted, {n_rej} rejected ({reject_pct:.1f}% rejected)")

    # Download PDFs
    logger.info("Downloading PDFs...")
    all_papers = download_papers(
        papers=all_papers,
        output_dir=output_dir,
        rate_limit_delay=0.5,
    )

    # Save
    config = SourcingConfig(
        conferences=[Conference.ICLR, Conference.NEURIPS, Conference.ICML],
        years=years,
        papers_per_conference=50,  # Not accurate but placeholder
        top_tier_per_conference=0,
        seed=seed,
    )

    result = SourcingResult(
        config=config,
        papers=all_papers,
        errors=[],
    )

    save_papers_json(result=result, output_path=output_dir / "papers.json")
    save_papers_csv(papers=all_papers, output_path=output_dir / "papers.csv")

    print("\nTest set created:")
    print(f"  Total: {len(all_papers)} papers")
    print(f"  Accepted: {n_acc}")
    print(f"  Rejected: {n_rej}")
    print(f"  Output: {output_dir}")


if __name__ == "__main__":
    main()
