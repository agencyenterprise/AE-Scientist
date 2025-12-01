from typing import List

from pydantic import BaseModel, Field


class TrainingReview(BaseModel):
    is_bug: bool = Field(
        ...,
        description="True if the output log shows a failure or bug; False when execution succeeded.",
    )
    summary: str = Field(
        ...,
        description="If is_bug=True, summarize the failure and propose a fix. Otherwise leave empty.",
    )


class PlotAnalysisEntry(BaseModel):
    analysis: str = Field(
        ...,
        description="Detailed analysis of the plot's implications and scientific insight.",
    )


class PlotFeedback(BaseModel):
    plot_analyses: List[PlotAnalysisEntry] = Field(
        ...,
        description="Per-plot analyses to surface in the write-up. Include at most the plots worth discussing.",
    )
    valid_plots_received: bool = Field(
        ...,
        description=(
            "True if the provided plots were meaningful. "
            "Set False when plots are empty/corrupted/non-diagnostic."
        ),
    )
    vlm_feedback_summary: str = Field(
        ...,
        description="High-level summary of the vision-language model feedback (focus on generated samples when relevant).",
    )


class MetricDataPoint(BaseModel):
    dataset_name: str = Field(
        ...,
        description="Name of the dataset without 'train', 'val', or 'test' suffixes.",
    )
    final_value: float
    best_value: float


class MetricInfo(BaseModel):
    metric_name: str = Field(
        ...,
        description=(
            "Specific metric name (e.g., 'validation accuracy', 'BLEU-4'); "
            "avoid vague labels like 'train' or 'test'."
        ),
    )
    lower_is_better: bool = Field(
        ...,
        description="Whether lower values are better for this metric.",
    )
    description: str = Field(
        ...,
        description="Short explanation of what the metric captures.",
    )
    data: List[MetricDataPoint] = Field(
        ...,
        description="Per-dataset measurements for this metric.",
    )


class MetricParseResponse(BaseModel):
    valid_metrics_received: bool = Field(
        ...,
        description="True if any metrics were parsed from the execution output; False when output lacked metrics.",
    )
    metric_names: List[MetricInfo] = Field(
        ...,
        description="Collection of metrics parsed from the logs. Leave empty when valid_metrics_received=False.",
    )


class PlotSelectionResponse(BaseModel):
    selected_plots: List[str] = Field(
        ...,
        description="Full paths of up to 10 plots that best capture results (ordered by importance).",
    )


class ExperimentSummary(BaseModel):
    findings: str = Field(
        ...,
        description="Key experimental findings/outcomes.",
    )
    significance: str = Field(
        ...,
        description="Why the findings matter and the insight they provide.",
    )
    next_steps: str | None = Field(
        default=None,
        description="Follow-up experiments or improvements (optional).",
    )


REVIEW_RESPONSE_SCHEMA = TrainingReview
VLM_FEEDBACK_SCHEMA = PlotFeedback
METRIC_PARSE_SCHEMA = MetricParseResponse
PLOT_SELECTION_SCHEMA = PlotSelectionResponse
SUMMARY_RESPONSE_SCHEMA = ExperimentSummary
