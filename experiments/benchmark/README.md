# Benchmark

Evaluate ae-paper-review against OpenReview ground truth scores.

## Overview

This module runs the ae-paper-review system on sourced papers and computes correlation metrics against actual reviewer scores and decisions.

## Metrics

### Primary Metrics ("Are we credible?")

| Metric | Description | Target |
|--------|-------------|--------|
| **Spearman's ρ** | Correlation between system score (1-10) and average reviewer score | >0.5 respectable, >0.6 strong |
| **AUC-ROC** | Accept/reject classification at optimal threshold | Higher is better |

### Secondary Metrics ("Are we calibrated?")

| Metric | Description |
|--------|-------------|
| **Cohen's d** | Effect size between accepted vs rejected mean scores |
| **Precision** | True accepts / Predicted accepts |
| **Recall** | True accepts / Actual accepts |
| **F1 Score** | Harmonic mean of precision and recall |
| **Accuracy** | Overall classification accuracy |
| **Confusion Matrix** | TP, FP, TN, FN counts |

### Planned Metrics (Not Yet Implemented)

- Per-conference Spearman's ρ breakdown
- 95% bootstrap confidence intervals
- Cohen's κ (inter-rater agreement)
- Score distribution histograms

## Usage

### Run Single Benchmark

```bash
cd experiments
source .env  # Load API keys

python -m benchmark.cli \
    --papers-json ./data_50/papers.json \
    --pdf-base-path ./data_50 \
    --output ./results.json \
    --model anthropic:claude-opus-4-6 \
    --num-reflections 1 \
    --num-ensemble 3
```

### Run Multiple Configurations

Compare models with identical settings:

```bash
# Run all 4 model configs sequentially
python -m benchmark.run_configs \
    --papers-json ./data_50/papers.json \
    --pdf-base-path ./data_50 \
    --output-dir ./data_50/benchmark_results

# Run specific config
python -m benchmark.run_configs --config grok-reasoning
```

### Run in Parallel (by provider)

Since each provider has independent rate limits:

```bash
# Terminal 1 (xai)
python -m benchmark.run_configs --config grok-reasoning

# Terminal 2 (openai)
python -m benchmark.run_configs --config gpt-5.2

# Terminal 3 (anthropic)
python -m benchmark.run_configs --config claude-opus

# After grok-reasoning finishes, run grok-non-reasoning
python -m benchmark.run_configs --config grok-non-reasoning
```

## Configurations

All configs use production settings:
- `num_reviews_ensemble=3` - 3 independent reviews aggregated
- `num_reflections=1` - 1 reflection round per review
- `num_fs_examples=1` - 1 few-shot example
- `temperature=1` - Standard temperature

| Config | Model | Purpose |
|--------|-------|---------|
| `grok-reasoning` | xai:grok-4-1-fast-reasoning | Reasoning baseline |
| `grok-non-reasoning` | xai:grok-4-1-fast-non-reasoning | Reasoning vs non-reasoning |
| `gpt-5.2` | openai:gpt-5.2 | Cross-provider comparison |
| `claude-opus` | anthropic:claude-opus-4-6 | Cross-provider comparison |

## Auto-Resume

Benchmarks automatically resume from the output file if interrupted:
- Completed papers are skipped
- Failed papers are retried
- Progress is saved after each paper

To start fresh, delete the output file or use `--fresh` flag.

## Output

### Results JSON Schema

```json
{
  "config": {
    "model": "anthropic:claude-opus-4-6",
    "temperature": 1,
    "num_reflections": 1,
    "num_fs_examples": 1,
    "num_reviews_ensemble": 3,
    "max_papers": 50
  },
  "paper_results": [
    {
      "paper_id": "abc123",
      "conference": "ICLR",
      "year": 2024,
      "sample_category": "random",
      "real_average_score": 7.5,
      "real_decision": "Accept (Spotlight)",
      "real_presentation_tier": "spotlight",
      "generated_overall": 8.0,
      "generated_decision": "Accept",
      "generated_confidence": 4.0,
      "input_tokens": 45000,
      "output_tokens": 2500,
      "model": "anthropic:claude-opus-4-6",
      "reviewed_at": "2024-02-17T10:30:00",
      "error": null
    }
  ],
  "metrics": {
    "n_total": 50,
    "n_with_scores": 48,
    "n_accepted": 18,
    "n_rejected": 32,
    "spearman_rho_full": 0.52,
    "spearman_pvalue_full": 0.001,
    "auc_roc": 0.78,
    "cohens_d": 1.2,
    "accuracy": 0.72,
    "precision": 0.75,
    "recall": 0.68,
    "f1_score": 0.71,
    "true_positives": 12,
    "false_positives": 4,
    "true_negatives": 24,
    "false_negatives": 6
  },
  "started_at": "2024-02-17T10:00:00",
  "completed_at": "2024-02-17T12:30:00"
}
```

### Comparison Summary

After running multiple configs, a summary is generated:

```
================================================================================
CONFIGURATION COMPARISON
================================================================================
Config                    Spearman ρ    AUC-ROC       F1  Accuracy       Tokens
--------------------------------------------------------------------------------
claude-opus                    0.523      0.782    0.714     72.0%      2,450,000
gpt-5.2                        0.498      0.756    0.689     70.0%      2,100,000
grok-reasoning                 0.512      0.768    0.701     71.0%      1,950,000
grok-non-reasoning             0.445      0.721    0.654     68.0%      1,800,000
================================================================================

Recommended config: claude-opus
  AUC-ROC: 0.782
  Spearman ρ: 0.523
```

## Module Structure

```
benchmark/
├── __init__.py
├── models.py          # Pydantic models (BenchmarkConfig, BenchmarkResult, etc.)
├── metrics.py         # Spearman, AUC-ROC, Cohen's d, confusion matrix
├── runner.py          # Core benchmark runner with auto-resume
├── cli.py             # Single-model CLI
├── run_configs.py     # Multi-model comparison runner
└── sample_test_set.py # 50-paper test set generator
```

## Test Set (50 papers)

The 50-paper test set was created with:
- **ICLR**: 25 papers (5 accepted, 20 rejected)
- **NeurIPS**: 15 papers (3 accepted, 12 rejected)
- **ICML**: 10 papers (10 accepted, 0 rejected - no rejected available)
- **Total**: 50 papers (18 accepted, 32 rejected = 64% rejection rate)

Generate with:
```bash
python -m benchmark.sample_test_set
```

## Workflow

1. **Source papers**: Use paper_sourcing to get 50 or 300 papers
2. **Run 50-paper benchmark**: Test 4 model configs in parallel
3. **Compare results**: Pick best performing model
4. **Run 300-paper calibration**: Full benchmark with selected model
5. **Report metrics**: Spearman's ρ, AUC-ROC, Cohen's d, F1

## Environment Variables

Required in `.env`:
```
OPENAI_API_KEY=...
XAI_API_KEY=...
ANTHROPIC_API_KEY=...
```
