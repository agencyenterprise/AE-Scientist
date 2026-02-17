"""Metric calculations for benchmark evaluation."""

import math
import random

from scipy import stats  # type: ignore[import-untyped]
from sklearn.metrics import (  # type: ignore[import-untyped]
    accuracy_score,
    cohen_kappa_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)

from .models import (
    BenchmarkMetrics,
    ConfidenceInterval,
    ConferenceMetrics,
    CorrelationResult,
    PaperReviewResult,
)


def is_accepted(decision: str) -> bool:
    """Check if a decision string indicates acceptance."""
    decision_lower = decision.lower()
    return "accept" in decision_lower and "reject" not in decision_lower


def compute_spearman_correlation(
    *,
    real_scores: list[float],
    generated_scores: list[float],
) -> CorrelationResult:
    """Compute Spearman rank correlation between real and generated scores.

    Args:
        real_scores: List of real reviewer scores
        generated_scores: List of generated scores

    Returns:
        CorrelationResult with correlation coefficient and p-value
    """
    if len(real_scores) < 3:
        return CorrelationResult(correlation=0.0, pvalue=1.0)

    result = stats.spearmanr(real_scores, generated_scores)
    correlation = float(result.statistic)
    pvalue = float(result.pvalue)

    # Handle NaN (e.g., when all values are identical)
    if math.isnan(correlation):
        return CorrelationResult(correlation=0.0, pvalue=1.0)

    return CorrelationResult(correlation=correlation, pvalue=pvalue)


def compute_bootstrap_ci(
    *,
    real_scores: list[float],
    generated_scores: list[float],
    n_bootstrap: int,
    confidence: float,
    seed: int,
) -> ConfidenceInterval | None:
    """Compute bootstrap confidence interval for Spearman's rho.

    Args:
        real_scores: List of real reviewer scores
        generated_scores: List of generated scores
        n_bootstrap: Number of bootstrap samples
        confidence: Confidence level (e.g., 0.95)
        seed: Random seed for reproducibility

    Returns:
        ConfidenceInterval or None if insufficient data
    """
    if len(real_scores) < 5:
        return None

    rng = random.Random(seed)
    n = len(real_scores)
    bootstrap_rhos: list[float] = []

    for _ in range(n_bootstrap):
        # Sample with replacement
        indices = [rng.randint(0, n - 1) for _ in range(n)]
        boot_real = [real_scores[i] for i in indices]
        boot_gen = [generated_scores[i] for i in indices]

        # Compute Spearman for this bootstrap sample
        try:
            result = stats.spearmanr(boot_real, boot_gen)
            rho = float(result.statistic)
            if not math.isnan(rho):
                bootstrap_rhos.append(rho)
        except Exception:
            continue

    if len(bootstrap_rhos) < n_bootstrap * 0.5:
        return None

    # Compute percentiles
    bootstrap_rhos.sort()
    alpha = 1 - confidence
    lower_idx = int(len(bootstrap_rhos) * (alpha / 2))
    upper_idx = int(len(bootstrap_rhos) * (1 - alpha / 2))

    return ConfidenceInterval(
        lower=bootstrap_rhos[lower_idx],
        upper=bootstrap_rhos[min(upper_idx, len(bootstrap_rhos) - 1)],
    )


def compute_per_conference_metrics(
    *,
    results: list[PaperReviewResult],
) -> list[ConferenceMetrics]:
    """Compute Spearman's rho per conference.

    Args:
        results: List of paper review results

    Returns:
        List of ConferenceMetrics, one per conference
    """
    # Group by conference
    by_conference: dict[str, list[PaperReviewResult]] = {}
    for r in results:
        if r.conference not in by_conference:
            by_conference[r.conference] = []
        by_conference[r.conference].append(r)

    conference_metrics: list[ConferenceMetrics] = []

    for conference, conf_results in sorted(by_conference.items()):
        # Filter to papers with valid scores
        valid = [r for r in conf_results if r.real_average_score > 0]

        if len(valid) < 3:
            conference_metrics.append(
                ConferenceMetrics(
                    conference=conference,
                    n_papers=len(conf_results),
                    spearman_rho=0.0,
                    spearman_pvalue=1.0,
                )
            )
            continue

        real_scores = [r.real_average_score for r in valid]
        gen_scores = [r.generated_overall for r in valid]

        corr = compute_spearman_correlation(
            real_scores=real_scores,
            generated_scores=gen_scores,
        )

        conference_metrics.append(
            ConferenceMetrics(
                conference=conference,
                n_papers=len(conf_results),
                spearman_rho=corr.correlation,
                spearman_pvalue=corr.pvalue,
            )
        )

    return conference_metrics


def compute_cohens_d(
    *,
    group1: list[float],
    group2: list[float],
) -> float:
    """Compute Cohen's d effect size between two groups.

    Args:
        group1: First group of values
        group2: Second group of values

    Returns:
        Cohen's d effect size
    """
    if len(group1) < 2 or len(group2) < 2:
        return 0.0

    mean1 = sum(group1) / len(group1)
    mean2 = sum(group2) / len(group2)

    var1 = sum((x - mean1) ** 2 for x in group1) / (len(group1) - 1)
    var2 = sum((x - mean2) ** 2 for x in group2) / (len(group2) - 1)

    # Pooled standard deviation
    pooled_std = math.sqrt(
        ((len(group1) - 1) * var1 + (len(group2) - 1) * var2) / (len(group1) + len(group2) - 2)
    )

    if pooled_std == 0:
        return 0.0

    return (mean1 - mean2) / pooled_std


def compute_metrics(*, results: list[PaperReviewResult]) -> BenchmarkMetrics:
    """Compute all benchmark metrics from paper review results.

    Args:
        results: List of paper review results

    Returns:
        BenchmarkMetrics with all computed metrics
    """
    # Filter out failed reviews
    valid_results = [r for r in results if r.error is None]

    if not valid_results:
        return BenchmarkMetrics(
            spearman_rho_full=0.0,
            spearman_pvalue_full=1.0,
            spearman_rho_random_only=0.0,
            spearman_pvalue_random_only=1.0,
            auc_roc=0.5,
            accuracy=0.0,
            precision=0.0,
            recall=0.0,
            f1_score=0.0,
            cohens_d=0.0,
            true_positives=0,
            true_negatives=0,
            false_positives=0,
            false_negatives=0,
            n_total=0,
            n_random=0,
            n_top_tier=0,
            n_accepted=0,
            n_rejected=0,
        )

    # Split by sample category
    random_results = [r for r in valid_results if r.sample_category == "random"]
    top_tier_results = [r for r in valid_results if r.sample_category == "top_tier"]

    # Extract score pairs for Spearman correlation
    # Note: ICML papers may have 0.0 scores (no public scores), filter them out
    valid_score_results = [r for r in valid_results if r.real_average_score > 0]
    real_scores_full = [r.real_average_score for r in valid_score_results]
    generated_scores_full = [r.generated_overall for r in valid_score_results]

    valid_random_results = [r for r in random_results if r.real_average_score > 0]
    real_scores_random = [r.real_average_score for r in valid_random_results]
    generated_scores_random = [r.generated_overall for r in valid_random_results]

    # Compute Spearman correlations
    spearman_full = compute_spearman_correlation(
        real_scores=real_scores_full,
        generated_scores=generated_scores_full,
    )
    spearman_random = compute_spearman_correlation(
        real_scores=real_scores_random,
        generated_scores=generated_scores_random,
    )

    # Classification metrics: real accept/reject vs generated
    real_accepted = [is_accepted(r.real_decision) for r in valid_results]
    generated_accepted = [is_accepted(r.generated_decision) for r in valid_results]

    # Convert to binary (1=Accept, 0=Reject)
    y_true = [1 if a else 0 for a in real_accepted]
    y_pred = [1 if a else 0 for a in generated_accepted]

    # Confusion matrix
    if sum(y_true) > 0 and sum(y_true) < len(y_true):
        tn, fp, fn, tp = confusion_matrix(y_true, y_pred).ravel()
        accuracy = accuracy_score(y_true, y_pred)
        precision = precision_score(y_true, y_pred, zero_division=0.0)
        recall = recall_score(y_true, y_pred, zero_division=0.0)
        f1 = f1_score(y_true, y_pred, zero_division=0.0)

        # AUC-ROC uses generated overall score as probability
        # Normalize to 0-1 range
        y_scores = [r.generated_overall / 10.0 for r in valid_results]
        auc = roc_auc_score(y_true, y_scores)
    else:
        # All same class - can't compute meaningful classification metrics
        tp, tn, fp, fn = 0, 0, 0, 0
        accuracy = 0.0
        precision = 0.0
        recall = 0.0
        f1 = 0.0
        auc = 0.5

    # Cohen's d: difference in generated scores between accepted and rejected papers
    accepted_scores = [r.generated_overall for r in valid_results if is_accepted(r.real_decision)]
    rejected_scores = [
        r.generated_overall for r in valid_results if not is_accepted(r.real_decision)
    ]
    cohens_d = compute_cohens_d(group1=accepted_scores, group2=rejected_scores)

    # Bootstrap confidence intervals for Spearman's rho
    ci_full = compute_bootstrap_ci(
        real_scores=real_scores_full,
        generated_scores=generated_scores_full,
        n_bootstrap=1000,
        confidence=0.95,
        seed=42,
    )
    ci_random = compute_bootstrap_ci(
        real_scores=real_scores_random,
        generated_scores=generated_scores_random,
        n_bootstrap=1000,
        confidence=0.95,
        seed=42,
    )

    # Per-conference metrics
    per_conf = compute_per_conference_metrics(results=valid_results)

    # Cohen's kappa for inter-rater agreement
    cohens_kappa = cohen_kappa_score(y_true, y_pred)

    return BenchmarkMetrics(
        spearman_rho_full=spearman_full.correlation,
        spearman_pvalue_full=spearman_full.pvalue,
        spearman_ci_full=ci_full,
        spearman_rho_random_only=spearman_random.correlation,
        spearman_pvalue_random_only=spearman_random.pvalue,
        spearman_ci_random_only=ci_random,
        per_conference_metrics=per_conf,
        auc_roc=float(auc),
        accuracy=float(accuracy),
        precision=float(precision),
        recall=float(recall),
        f1_score=float(f1),
        cohens_d=cohens_d,
        cohens_kappa=float(cohens_kappa),
        true_positives=int(tp),
        true_negatives=int(tn),
        false_positives=int(fp),
        false_negatives=int(fn),
        n_total=len(valid_results),
        n_random=len(random_results),
        n_top_tier=len(top_tier_results),
        n_accepted=sum(y_true),
        n_rejected=len(y_true) - sum(y_true),
    )
