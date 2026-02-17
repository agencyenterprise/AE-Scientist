# Experiments

Benchmark and evaluation scripts for ae-paper-review against OpenReview ground truth.

## Overview

This module evaluates the ae-paper-review system by:
1. Sourcing papers with reviewer scores from OpenReview (ICLR, NeurIPS, ICML)
2. Running the review system on those papers
3. Computing correlation metrics against actual reviewer scores

## Workflow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ 1. Source Papers                                                            │
│    python -m paper_sourcing.cli --output-dir ./data                         │
│    → 300 papers: 100 per conference, 85 random + 15 top-tier each           │
└─────────────────────────────────────────────────────────────────────────────┘
                                     ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│ 2. Create 50-Paper Test Set                                                 │
│    python -m benchmark.sample_test_set                                      │
│    → 50 papers with balanced accept/reject ratio                            │
└─────────────────────────────────────────────────────────────────────────────┘
                                     ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│ 3. Run Model Comparison (50 papers)                                         │
│    python -m benchmark.run_configs --config <model>                         │
│    → Test 4 models in parallel (one per provider)                           │
└─────────────────────────────────────────────────────────────────────────────┘
                                     ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│ 4. Compare Results & Select Best Model                                      │
│    → Review comparison_summary.json                                         │
│    → Pick model with highest AUC-ROC / Spearman ρ                           │
└─────────────────────────────────────────────────────────────────────────────┘
                                     ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│ 5. Full 300-Paper Calibration                                               │
│    python -m benchmark.cli --model <best_model> --papers-json ./data/...    │
│    → Final metrics with selected model                                      │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Setup

```bash
cd experiments
uv sync
```

Create `.env` with API keys:
```
OPENAI_API_KEY=...
XAI_API_KEY=...
ANTHROPIC_API_KEY=...
```

## Quick Start

```bash
# 1. Create 50-paper test set (already done in data_50/)
python -m benchmark.sample_test_set

# 2. Run benchmarks in parallel (3 terminals)
source .env
nohup python -m benchmark.run_configs --config grok-reasoning > logs/grok.log 2>&1 &
nohup python -m benchmark.run_configs --config gpt-5.2 > logs/gpt.log 2>&1 &
nohup python -m benchmark.run_configs --config claude-opus > logs/claude.log 2>&1 &

# 3. Monitor progress
tail -f logs/*.log

# 4. After grok-reasoning finishes, run grok-non-reasoning
nohup python -m benchmark.run_configs --config grok-non-reasoning > logs/grok-nr.log 2>&1 &
```

## Modules

| Module | Description | README |
|--------|-------------|--------|
| [paper_sourcing/](paper_sourcing/) | OpenReview API client and paper sampling | [paper_sourcing/README.md](paper_sourcing/README.md) |
| [benchmark/](benchmark/) | Benchmark runner and metrics | [benchmark/README.md](benchmark/README.md) |

## Metrics

### Primary ("Are we credible?")

| Metric | Description | Target |
|--------|-------------|--------|
| **Spearman's ρ** | Score correlation with reviewers | >0.5 respectable, >0.6 strong |
| **AUC-ROC** | Accept/reject classification | Higher is better |

### Secondary ("Are we calibrated?")

| Metric | Description |
|--------|-------------|
| **Cohen's d** | Effect size between accepted/rejected scores |
| **F1 Score** | Precision-recall balance |
| **Confusion Matrix** | TP, FP, TN, FN breakdown |

## Model Configurations

| Config | Model | Notes |
|--------|-------|-------|
| `grok-reasoning` | xai:grok-4-1-fast-reasoning | Reasoning baseline |
| `grok-non-reasoning` | xai:grok-4-1-fast-non-reasoning | Compare reasoning impact |
| `gpt-5.2` | openai:gpt-5.2 | Cross-provider |
| `claude-opus` | anthropic:claude-opus-4-6 | Cross-provider |

All configs use: 3 ensemble reviews, 1 reflection, temperature=1

## Directory Structure

```
experiments/
├── paper_sourcing/       # OpenReview API and sampling
├── benchmark/            # Benchmark runner and metrics
├── data/                 # Full 300-paper dataset (gitignored)
├── data_50/              # 50-paper test set
│   ├── papers.json
│   ├── papers.csv
│   ├── pdfs/
│   └── benchmark_results/
├── .env                  # API keys (gitignored)
├── pyproject.toml
├── Makefile
└── README.md
```

## Development

```bash
# Install with dev dependencies
make install

# Run linters (black, isort, ruff, mypy, pyright, vulture)
make lint
```
