# Paper Sourcing

Source papers from OpenReview for benchmark evaluation against reviewer scores.

## Overview

This module fetches paper metadata and PDFs from the OpenReview API for ICLR, NeurIPS, and ICML conferences. It supports stratified sampling to ensure representation across acceptance tiers.

## Sampling Strategy

For each conference, papers are sampled as:
- **85 random** from the full submission pool (accepted + rejected)
- **15 top-tier** from oral/spotlight/best paper categories

This ensures enough density at the high end to verify the system can distinguish "good" from "excellent" without distorting the overall distribution.

### Conference Support

| Conference | API Version | Reviewer Scores | Rejected Papers |
|------------|-------------|-----------------|-----------------|
| ICLR | V2 | ✅ Full scores | ✅ Available |
| NeurIPS | V2 | ✅ Full scores | ✅ Available |
| ICML | V2 | ❌ Not public | ❌ Not available |

ICML only has accepted papers publicly available, so the sampling adjusts accordingly.

## Usage

### Full Paper Sourcing (~300 papers)

```bash
cd experiments
uv sync

python -m paper_sourcing.cli \
    --output-dir ./data \
    --conferences ICLR NeurIPS ICML \
    --years 2024 2025 \
    --papers-per-conference 100 \
    --top-tier-per-conference 15 \
    --seed 42
```

### Custom Sampling

```bash
# Source 50 papers from ICLR only
python -m paper_sourcing.cli \
    --output-dir ./data_iclr \
    --conferences ICLR \
    --years 2024 2025 \
    --papers-per-conference 50 \
    --top-tier-per-conference 10 \
    --seed 42

# Skip PDF download (metadata only)
python -m paper_sourcing.cli \
    --output-dir ./data \
    --skip-pdf-download
```

## Output

```
data/
├── papers.json      # Full metadata with sampling info
├── papers.csv       # CSV for easy analysis
└── pdfs/
    ├── ICLR/
    │   └── 2024/
    │       └── <paper_id>.pdf
    ├── NeurIPS/
    └── ICML/
```

### papers.json Schema

```json
{
  "config": {
    "conferences": ["ICLR", "NeurIPS", "ICML"],
    "years": [2024, 2025],
    "papers_per_conference": 100,
    "top_tier_per_conference": 15,
    "seed": 42
  },
  "papers": [
    {
      "paper_id": "abc123",
      "title": "Paper Title",
      "conference": "ICLR",
      "year": 2024,
      "reviewer_scores": [
        {"reviewer_id": "R1", "score": 8.0, "confidence": 4.0}
      ],
      "average_score": 7.5,
      "decision": "Accept (Spotlight)",
      "presentation_tier": "spotlight",
      "sample_category": "top_tier",
      "pdf_path": "pdfs/ICLR/2024/abc123.pdf"
    }
  ]
}
```

## Module Structure

```
paper_sourcing/
├── __init__.py
├── models.py              # Pydantic models (PaperMetadata, ReviewerScore, etc.)
├── openreview_client.py   # OpenReview API wrapper
├── sampler.py             # Stratified sampling logic
└── cli.py                 # CLI entry point
```

### Key Components

- **models.py**: Data models for papers, scores, and configuration
- **openreview_client.py**: Handles API V1/V2, extracts scores and decisions
- **sampler.py**: Implements 85/15 random/top-tier sampling
- **cli.py**: CLI with PDF download and progress tracking

## Presentation Tiers

Papers are categorized into tiers based on their decision:

| Tier | Examples |
|------|----------|
| `best_paper` | Best Paper Award, Outstanding Paper |
| `oral` | Oral presentation, Notable Top-5% |
| `spotlight` | Spotlight, Notable Top-25% |
| `poster` | Poster, Accept |
| `reject` | Reject |
| `unknown` | Withdrawn, unclear decision |

## Rate Limiting

The CLI includes a configurable delay between PDF downloads (default: 0.5s) to respect OpenReview's rate limits.

## Verification

After sourcing, verify the dataset:

```bash
# Check paper counts
jq '.papers | length' data/papers.json

# Check tier distribution
jq '.papers | group_by(.presentation_tier) | map({tier: .[0].presentation_tier, count: length})' data/papers.json

# Check accept/reject split
jq '.papers | group_by(.decision | test("reject"; "i")) | map({rejected: .[0].decision, count: length})' data/papers.json
```
