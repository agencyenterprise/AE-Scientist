"""Pydantic models for paper review."""

from typing import List, Literal

from pydantic import BaseModel, Field


class ReviewResponseModel(BaseModel):
    """Structured response model for LLM paper review."""

    summary: str = Field(
        ..., alias="Summary", description="Faithful summary of the paper and its contributions."
    )
    strengths: List[str] = Field(
        default_factory=list,
        alias="Strengths",
        description="Bullet-style strengths highlighting novelty, rigor, clarity, etc.",
    )
    weaknesses: List[str] = Field(
        default_factory=list,
        alias="Weaknesses",
        description="Specific weaknesses or missing evidence.",
    )
    originality: int = Field(
        ...,
        alias="Originality",
        description="Rating 1-4 (low to very high) for originality/novelty.",
        ge=1,
        le=4,
    )
    quality: int = Field(
        ...,
        alias="Quality",
        description="Rating 1-4 for technical quality and correctness.",
        ge=1,
        le=4,
    )
    clarity: int = Field(
        ...,
        alias="Clarity",
        description="Rating 1-4 for clarity and exposition quality.",
        ge=1,
        le=4,
    )
    significance: int = Field(
        ...,
        alias="Significance",
        description="Rating 1-4 for potential impact/significance.",
        ge=1,
        le=4,
    )
    questions: List[str] = Field(
        default_factory=list,
        alias="Questions",
        description="Clarifying questions for the authors.",
    )
    limitations: List[str] = Field(
        default_factory=list,
        alias="Limitations",
        description="Limitation notes or identified risks.",
    )
    ethical_concerns: bool = Field(
        ...,
        alias="Ethical_Concerns",
        description="True if ethical concerns exist, False otherwise.",
    )
    soundness: int = Field(
        ...,
        alias="Soundness",
        description="Rating 1-4 for methodological soundness.",
        ge=1,
        le=4,
    )
    presentation: int = Field(
        ...,
        alias="Presentation",
        description="Rating 1-4 for presentation quality.",
        ge=1,
        le=4,
    )
    contribution: int = Field(
        ...,
        alias="Contribution",
        description="Rating 1-4 for contribution level.",
        ge=1,
        le=4,
    )
    overall: int = Field(
        ...,
        alias="Overall",
        description="Overall rating 1-10 (1=reject, 10=award level).",
        ge=1,
        le=10,
    )
    confidence: int = Field(
        ...,
        alias="Confidence",
        description="Confidence rating 1-5 (1=guessing, 5=absolutely certain).",
        ge=1,
        le=5,
    )
    decision: Literal["Accept", "Reject"] = Field(
        ...,
        alias="Decision",
        description='Final decision string ("Accept" or "Reject").',
    )
    should_continue: bool = Field(
        default=True,
        description="For reflection loops; set false when no further updates required.",
    )

    class Config:
        populate_by_name = True


class ImageCaptionRefReview(BaseModel):
    """Structured response model for VLM figure caption/reference review."""

    img_description: str = Field(
        ...,
        alias="Img_description",
        description="Describe the figure's contents, axes, and notable patterns.",
    )
    img_review: str = Field(
        ...,
        alias="Img_review",
        description="Analysis of the figure quality, clarity, and potential improvements.",
    )
    caption_review: str = Field(
        ...,
        alias="Caption_review",
        description="Assessment of how well the caption matches and explains the figure.",
    )
    figrefs_review: str = Field(
        ...,
        alias="Figrefs_review",
        description="Evaluation of how the main text references integrate this figure.",
    )

    class Config:
        populate_by_name = True


class ImageSelectionReview(ImageCaptionRefReview):
    """Extended review model for figure selection decisions."""

    overall_comments: str = Field(
        ...,
        alias="Overall_comments",
        description="Whether the figure adds sufficient value given page limits.",
    )
    containing_sub_figures: str = Field(
        ...,
        alias="Containing_sub_figures",
        description="Whether the figure has subplots and if their layout is adequate.",
    )
    informative_review: str = Field(
        ...,
        alias="Informative_review",
        description="Whether the figure is informative or redundant.",
    )


class ImageReview(BaseModel):
    """Simple image review model."""

    img_description: str = Field(
        ...,
        alias="Img_description",
        description="Describe the figure's contents in detail.",
    )
    img_review: str = Field(
        ...,
        alias="Img_review",
        description="Critique or suggestions for improving the figure.",
    )

    class Config:
        populate_by_name = True


class FigureImageCaptionRefReview(BaseModel):
    """Combined figure review with identifier."""

    figure_name: str = Field(..., description="Normalized identifier for the figure.")
    review: ImageCaptionRefReview
