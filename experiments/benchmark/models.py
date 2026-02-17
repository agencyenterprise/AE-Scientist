"""Pydantic models for benchmark results."""

from datetime import datetime
from typing import NamedTuple

from pydantic import BaseModel, Field


class PaperReviewResult(BaseModel):
    """Result of running ae-paper-review on a single paper."""

    paper_id: str = Field(description="OpenReview paper ID")
    conference: str = Field(description="Conference venue")
    year: int = Field(description="Conference year")
    sample_category: str = Field(description="random or top_tier")

    # Real OpenReview data
    real_average_score: float = Field(description="Real average reviewer score")
    real_decision: str = Field(description="Real decision string")
    real_presentation_tier: str = Field(description="Real presentation tier")

    # Generated review data
    generated_overall: float = Field(description="Generated overall score (1-10)")
    generated_decision: str = Field(description="Generated decision (Accept/Reject)")
    generated_confidence: float = Field(description="Generated confidence (1-5)")
    generated_originality: int = Field(description="Generated originality score (1-4)")
    generated_quality: int = Field(description="Generated quality score (1-4)")
    generated_clarity: int = Field(description="Generated clarity score (1-4)")
    generated_significance: int = Field(description="Generated significance score (1-4)")

    # Token usage
    input_tokens: int = Field(description="Input tokens used")
    output_tokens: int = Field(description="Output tokens used")

    # Metadata
    model: str = Field(description="Model used for review")
    reviewed_at: datetime = Field(description="When review was generated")
    error: str | None = Field(default=None, description="Error message if review failed")


class ConfidenceInterval(BaseModel):
    """95% confidence interval."""

    lower: float = Field(description="Lower bound (2.5th percentile)")
    upper: float = Field(description="Upper bound (97.5th percentile)")


class ConferenceMetrics(BaseModel):
    """Per-conference metrics."""

    conference: str = Field(description="Conference name")
    n_papers: int = Field(description="Number of papers")
    spearman_rho: float = Field(description="Spearman correlation")
    spearman_pvalue: float = Field(description="P-value")


class BenchmarkMetrics(BaseModel):
    """Computed metrics from benchmark results."""

    # Spearman's rho correlations
    spearman_rho_full: float = Field(description="Spearman correlation on all papers")
    spearman_pvalue_full: float = Field(description="P-value for full correlation")
    spearman_ci_full: ConfidenceInterval | None = Field(
        default=None, description="95% bootstrap CI for full Spearman"
    )
    spearman_rho_random_only: float = Field(
        description="Spearman correlation on random-only subset"
    )
    spearman_pvalue_random_only: float = Field(description="P-value for random-only correlation")
    spearman_ci_random_only: ConfidenceInterval | None = Field(
        default=None, description="95% bootstrap CI for random-only Spearman"
    )

    # Per-conference breakdown
    per_conference_metrics: list[ConferenceMetrics] = Field(
        default_factory=list, description="Spearman rho per conference"
    )

    # Accept/Reject classification metrics
    auc_roc: float = Field(description="AUC-ROC for accept/reject classification")
    accuracy: float = Field(description="Classification accuracy")
    precision: float = Field(description="Precision for Accept class")
    recall: float = Field(description="Recall for Accept class")
    f1_score: float = Field(description="F1 score for Accept class")

    # Effect size
    cohens_d: float = Field(description="Cohen's d effect size between accepted/rejected scores")

    # Inter-rater agreement
    cohens_kappa: float = Field(
        default=0.0, description="Cohen's kappa (system vs panel agreement)"
    )

    # Confusion matrix values
    true_positives: int = Field(description="True positives (Accept correctly predicted)")
    true_negatives: int = Field(description="True negatives (Reject correctly predicted)")
    false_positives: int = Field(description="False positives (Reject predicted as Accept)")
    false_negatives: int = Field(description="False negatives (Accept predicted as Reject)")

    # Sample sizes
    n_total: int = Field(description="Total papers evaluated")
    n_random: int = Field(description="Random-only papers")
    n_top_tier: int = Field(description="Top-tier papers")
    n_accepted: int = Field(description="Papers with Accept in real decision")
    n_rejected: int = Field(description="Papers with Reject in real decision")


class BenchmarkConfig(BaseModel):
    """Configuration for benchmark run."""

    model: str = Field(description="Model to use for reviews")
    temperature: float = Field(description="Sampling temperature")
    num_reflections: int = Field(description="Number of reflection rounds")
    num_fs_examples: int = Field(description="Number of few-shot examples")
    num_reviews_ensemble: int = Field(description="Number of ensemble reviews")
    max_papers: int | None = Field(description="Max papers to process (None for all)")


class BenchmarkResult(BaseModel):
    """Complete benchmark result."""

    config: BenchmarkConfig = Field(description="Benchmark configuration")
    paper_results: list[PaperReviewResult] = Field(description="Individual paper results")
    metrics: BenchmarkMetrics | None = Field(default=None, description="Computed metrics")
    started_at: datetime = Field(description="When benchmark started")
    completed_at: datetime | None = Field(default=None, description="When benchmark completed")
    errors: list[str] = Field(default_factory=list, description="Errors encountered")


class CorrelationResult(NamedTuple):
    """Correlation result with p-value."""

    correlation: float
    pvalue: float
