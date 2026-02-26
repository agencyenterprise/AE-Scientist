"""Pydantic models for VLM-based figure review."""

from pydantic import BaseModel, Field


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
