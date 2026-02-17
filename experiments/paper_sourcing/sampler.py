"""Sampling strategy for paper selection."""

import logging
import random
from datetime import datetime
from typing import Any

from .models import Conference, PaperMetadata, PresentationTier, SampleCategory, SourcingConfig
from .openreview_client import (
    VenueConfig,
    extract_decision,
    extract_reviewer_scores,
    fetch_submissions,
    get_pdf_url,
    get_title,
    get_venue_config,
)

# Filter out papers without PDFs since we need them for review
REQUIRE_PDF = True

logger = logging.getLogger(__name__)


# Recency weighting: 70% from most recent year, 30% from older years
RECENT_YEAR_WEIGHT = 0.70


def sample_papers_for_conference(
    *,
    conference: Conference,
    years: list[int],
    total_papers: int,
    top_tier_papers: int,
    seed: int,
) -> list[PaperMetadata]:
    """Sample papers from a conference across multiple years.

    Uses 70-30 recency split: 70% from most recent year, 30% from older.

    Args:
        conference: Conference to sample from
        years: Years to sample from (most recent year gets 70% weight)
        total_papers: Total papers to sample for this conference
        top_tier_papers: Number of top-tier papers to include
        seed: Random seed for reproducibility

    Returns:
        List of PaperMetadata for sampled papers
    """
    random_papers_needed = total_papers - top_tier_papers

    # Collect submissions grouped by year
    # year -> list of (note, venue_config, year)
    submissions_by_year: dict[int, list[tuple[Any, VenueConfig, int]]] = {}
    top_tier_by_year: dict[int, list[tuple[Any, VenueConfig, int]]] = {}

    for year in years:
        venue_config = get_venue_config(conference=conference, year=year)
        if venue_config is None:
            logger.warning(f"No venue config for {conference.value} {year}, skipping")
            continue

        try:
            submissions = fetch_submissions(config=venue_config)
        except Exception as e:
            logger.warning(f"Failed to fetch {conference.value} {year}: {e}")
            continue

        for note in submissions:
            decision_str, tier = extract_decision(note=note, api_version=venue_config.api_version)

            # Skip unknown decisions (no decision note found)
            if tier == PresentationTier.UNKNOWN:
                continue

            # For ICML, only include accepted papers (rejected papers don't have scores)
            if conference == Conference.ICML and tier == PresentationTier.REJECT:
                continue

            # Skip papers without PDFs if required
            if REQUIRE_PDF and not get_pdf_url(note=note):
                continue

            # Include all papers with known decisions (accepted OR rejected) in submission pool
            if year not in submissions_by_year:
                submissions_by_year[year] = []
            submissions_by_year[year].append((note, venue_config, year))

            # Top-tier = oral, spotlight, best paper
            if tier in (
                PresentationTier.ORAL,
                PresentationTier.SPOTLIGHT,
                PresentationTier.BEST_PAPER,
            ):
                if year not in top_tier_by_year:
                    top_tier_by_year[year] = []
                top_tier_by_year[year].append((note, venue_config, year))

    # Flatten for counting
    all_submissions = [item for year_list in submissions_by_year.values() for item in year_list]
    all_top_tier = [item for year_list in top_tier_by_year.values() for item in year_list]

    # Count accepted vs rejected
    accepted_count = sum(
        1
        for n, v, y in all_submissions
        if extract_decision(note=n, api_version=v.api_version)[1] != PresentationTier.REJECT
    )
    rejected_count = len(all_submissions) - accepted_count
    if conference == Conference.ICML:
        logger.info(
            f"{conference.value}: {len(all_submissions)} accepted papers (rejected excluded), "
            f"{len(all_top_tier)} top-tier"
        )
    else:
        logger.info(
            f"{conference.value}: {len(all_submissions)} total ({accepted_count} accepted, "
            f"{rejected_count} rejected), {len(all_top_tier)} top-tier"
        )

    # Initialize RNG with conference-specific seed
    # Use deterministic hash (sum of char codes) instead of Python's hash() which is randomized
    conference_offset = sum(ord(c) for c in conference.value)
    rng = random.Random(seed + conference_offset)

    # Apply 70-30 recency split: 70% from most recent year, 30% from older
    sorted_years = sorted(submissions_by_year.keys(), reverse=True)
    most_recent_year = sorted_years[0] if sorted_years else None
    older_years = sorted_years[1:] if len(sorted_years) > 1 else []

    # Calculate samples per year group with 70-30 split
    recent_random = int(random_papers_needed * RECENT_YEAR_WEIGHT)
    older_random = random_papers_needed - recent_random
    recent_top_tier = int(top_tier_papers * RECENT_YEAR_WEIGHT)
    older_top_tier = top_tier_papers - recent_top_tier

    logger.info(
        f"Recency split: {recent_random} random + {recent_top_tier} top-tier from {most_recent_year}, "
        f"{older_random} random + {older_top_tier} top-tier from {older_years}"
    )

    # Sample top-tier papers with recency weighting
    top_tier_sample: list[tuple[Any, VenueConfig, int]] = []

    # Recent year top-tier
    if most_recent_year and most_recent_year in top_tier_by_year:
        recent_pool = top_tier_by_year[most_recent_year]
        sample_size = min(recent_top_tier, len(recent_pool))
        top_tier_sample.extend(rng.sample(recent_pool, sample_size))

    # Older years top-tier
    older_pool = [
        item for yr in older_years if yr in top_tier_by_year for item in top_tier_by_year[yr]
    ]
    if older_pool:
        sample_size = min(older_top_tier, len(older_pool))
        top_tier_sample.extend(rng.sample(older_pool, sample_size))

    # If we didn't get enough from split, fill from any available
    remaining_top_tier = top_tier_papers - len(top_tier_sample)
    if remaining_top_tier > 0:
        top_tier_ids_so_far = {note.id for note, _, _ in top_tier_sample}
        remaining_pool = [item for item in all_top_tier if item[0].id not in top_tier_ids_so_far]
        if remaining_pool:
            sample_size = min(remaining_top_tier, len(remaining_pool))
            top_tier_sample.extend(rng.sample(remaining_pool, sample_size))

    top_tier_ids = {note.id for note, _, _ in top_tier_sample}

    # Sample random papers with recency weighting
    random_sample: list[tuple[Any, VenueConfig, int]] = []

    # Recent year random
    if most_recent_year and most_recent_year in submissions_by_year:
        recent_pool = [
            (n, v, y)
            for n, v, y in submissions_by_year[most_recent_year]
            if n.id not in top_tier_ids
        ]
        sample_size = min(recent_random, len(recent_pool))
        random_sample.extend(rng.sample(recent_pool, sample_size))

    # Older years random
    older_pool = [
        (n, v, y)
        for yr in older_years
        if yr in submissions_by_year
        for n, v, y in submissions_by_year[yr]
        if n.id not in top_tier_ids
    ]
    if older_pool:
        # Exclude already sampled
        sampled_ids = {n.id for n, _, _ in random_sample}
        older_pool = [(n, v, y) for n, v, y in older_pool if n.id not in sampled_ids]
        sample_size = min(older_random, len(older_pool))
        random_sample.extend(rng.sample(older_pool, sample_size))

    # If we didn't get enough from split, fill from any available
    remaining_random = random_papers_needed - len(random_sample)
    if remaining_random > 0:
        sampled_ids = {n.id for n, _, _ in random_sample} | top_tier_ids
        remaining_pool = [(n, v, y) for n, v, y in all_submissions if n.id not in sampled_ids]
        if remaining_pool:
            sample_size = min(remaining_random, len(remaining_pool))
            random_sample.extend(rng.sample(remaining_pool, sample_size))

    logger.info(
        f"Sampled {len(random_sample)} random + {len(top_tier_sample)} top-tier "
        f"from {conference.value}"
    )

    # Convert to PaperMetadata
    papers: list[PaperMetadata] = []
    now = datetime.now()

    for note, venue_config, year in random_sample:
        paper = _note_to_metadata(
            note=note,
            venue_config=venue_config,
            conference=conference,
            year=year,
            sample_category=SampleCategory.RANDOM,
            sourced_at=now,
        )
        papers.append(paper)

    for note, venue_config, year in top_tier_sample:
        paper = _note_to_metadata(
            note=note,
            venue_config=venue_config,
            conference=conference,
            year=year,
            sample_category=SampleCategory.TOP_TIER,
            sourced_at=now,
        )
        papers.append(paper)

    return papers


def _note_to_metadata(
    *,
    note: Any,  # noqa: ANN401 - openreview-py is untyped
    venue_config: VenueConfig,
    conference: Conference,
    year: int,
    sample_category: SampleCategory,
    sourced_at: datetime,
) -> PaperMetadata:
    """Convert an OpenReview note to PaperMetadata.

    Args:
        note: OpenReview submission note
        venue_config: Venue configuration
        conference: Conference enum
        year: Conference year
        sample_category: Random or top-tier
        sourced_at: Timestamp

    Returns:
        PaperMetadata instance
    """
    reviewer_scores = extract_reviewer_scores(note=note, api_version=venue_config.api_version)
    avg_score = (
        sum(s.score for s in reviewer_scores) / len(reviewer_scores) if reviewer_scores else 0.0
    )
    decision_str, tier = extract_decision(note=note, api_version=venue_config.api_version)

    return PaperMetadata(
        paper_id=note.id,
        title=get_title(note=note),
        conference=conference,
        year=year,
        venue_id=venue_config.venue_id,
        reviewer_scores=[(s.reviewer_id, s.score, s.confidence) for s in reviewer_scores],
        average_score=avg_score,
        decision=decision_str,
        presentation_tier=tier,
        sample_category=sample_category,
        pdf_url=get_pdf_url(note=note),
        pdf_path="",  # Filled in later during download
        sourced_at=sourced_at,
    )


def source_all_papers(*, config: SourcingConfig) -> tuple[list[PaperMetadata], list[str]]:
    """Source papers from all configured conferences.

    Args:
        config: Sourcing configuration

    Returns:
        Tuple of (papers, errors)
    """
    all_papers: list[PaperMetadata] = []
    errors: list[str] = []

    for conference in config.conferences:
        try:
            papers = sample_papers_for_conference(
                conference=conference,
                years=config.years,
                total_papers=config.papers_per_conference,
                top_tier_papers=config.top_tier_per_conference,
                seed=config.seed,
            )
            all_papers.extend(papers)
        except Exception as e:
            error_msg = f"Error processing {conference.value}: {e}"
            logger.error(error_msg)
            errors.append(error_msg)

    return all_papers, errors
