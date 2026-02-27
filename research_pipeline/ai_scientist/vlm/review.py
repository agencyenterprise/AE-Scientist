"""VLM-based figure review functionality."""

import hashlib
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, NamedTuple, Optional

import pymupdf
from ae_paper_review import Provider, TokenUsage
from ae_paper_review.llm import get_provider
from ae_paper_review.prompts import render_text as ae_render_text
from pydantic import BaseModel, ConfigDict, Field

from .client import get_response_from_vlm, get_structured_response_from_vlm
from .models import (
    FigureImageCaptionRefReview,
    ImageCaptionRefReview,
    ImageReview,
    ImageSelectionReview,
)
from .render import render_text

logger = logging.getLogger(__name__)


class FigureReviewResult(NamedTuple):
    """Result of figure review with token usage."""

    reviews: List[FigureImageCaptionRefReview]
    token_usage: TokenUsage


class FigureSelectionReviewResult(NamedTuple):
    """Result of figure selection review with token usage."""

    reviews: Dict[str, Any]
    token_usage: TokenUsage


class DuplicateFiguresResult(NamedTuple):
    """Result of duplicate figure detection with token usage."""

    analysis: str | Dict[str, str]
    token_usage: TokenUsage


class ImageReviewResult(NamedTuple):
    """Result of single image review with token usage."""

    review: Dict[str, Any] | None
    token_usage: TokenUsage


class AbstractExtractionResult(NamedTuple):
    """Result of abstract extraction from a PDF."""

    abstract: str
    token_usage: TokenUsage


class _PaperContextExtraction(BaseModel):
    """Extracted title and abstract from a paper."""

    title: str | None = Field(
        ...,
        alias="Title",
        description="The paper title. Set to null if not clearly present.",
    )
    abstract: str | None = Field(
        ...,
        alias="Abstract",
        description="The paper abstract. Set to null if not present.",
    )

    model_config = ConfigDict(populate_by_name=True, extra="forbid")


def _parse_provider_model(*, full_model: str) -> tuple[Provider, str]:
    """Parse a "provider:model" string into (Provider, model_name).

    Args:
        full_model: Model string in "provider:model" format (e.g., "anthropic:claude-sonnet-4-20250514")
    """
    parts = full_model.split(":", 1)
    if len(parts) != 2:
        raise ValueError(f"Expected 'provider:model' format, got: {full_model!r}")
    return Provider(parts[0]), parts[1]


def extract_abstract_from_pdf(*, pdf_path: Path, model: str) -> AbstractExtractionResult:
    """Extract abstract from a PDF using the provider's native PDF upload.

    Args:
        pdf_path: Path to the PDF file
        model: Model in "provider:model" format (e.g., "anthropic:claude-sonnet-4-20250514")

    Returns:
        AbstractExtractionResult with abstract text and token usage
    """
    provider, model_name = _parse_provider_model(full_model=model)
    usage = TokenUsage()
    try:
        llm = get_provider(provider=provider, model=model_name, usage=usage)
        file_id = llm.upload_pdf(pdf_path=pdf_path, filename="paper.pdf")
        try:
            result = llm.structured_chat(
                file_ids=[file_id],
                prompt=ae_render_text(
                    template_name="context_extraction/extract_context.txt.j2",
                    context={},
                ),
                system_message=ae_render_text(
                    template_name="context_extraction/system_prompt.txt.j2",
                    context={},
                ),
                temperature=0.1,
                schema_class=_PaperContextExtraction,
            )
            return AbstractExtractionResult(abstract=result.abstract or "", token_usage=usage)
        finally:
            try:
                llm.delete_file(file_id=file_id)
            except Exception:
                logger.warning("Failed to delete uploaded PDF file", exc_info=True)
    except Exception:
        logger.warning("Failed to extract abstract from PDF", exc_info=True)
        return AbstractExtractionResult(abstract="", token_usage=usage)


_reviewer_system_prompt_base = render_text(
    template_name="reviewer_system_prompt_base.txt.j2",
    context={},
)


class _ImgCapRefPromptContext(NamedTuple):
    abstract: str
    caption: str
    main_text_figrefs: str


class _ImgCapSelectionPromptContext(NamedTuple):
    abstract: str
    caption: str
    main_text_figrefs: str
    reflection_page_info: str


def extract_figure_screenshots(
    pdf_path: Path,
    img_folder_path: Path,
    num_pages: Optional[int] = None,
    min_text_length: int = 50,
    min_vertical_gap: int = 30,
) -> List[Dict[str, Any]]:
    """Extract screenshots for figure captions from a PDF.

    Args:
        pdf_path: Path to the PDF file
        img_folder_path: Directory to save extracted images
        num_pages: Optional limit on pages to process
        min_text_length: Minimum text length for blocks above figures
        min_vertical_gap: Minimum vertical gap between text and figure

    Returns:
        List of dicts with img_name, caption, images, main_text_figrefs
    """
    img_folder_path.mkdir(parents=True, exist_ok=True)
    doc = pymupdf.open(str(pdf_path))
    page_range = range(len(doc)) if num_pages is None else range(min(num_pages, len(doc)))

    text_blocks: List[Dict[str, Any]] = []
    for page_num in page_range:
        page = doc[page_num]
        try:
            blocks = page.get_text("blocks")  # type: ignore[attr-defined]
            for b in blocks:
                txt = b[4].strip()
                if txt:
                    bbox = pymupdf.Rect(b[0], b[1], b[2], b[3])
                    text_blocks.append({"page": page_num, "bbox": bbox, "text": txt})
        except Exception:
            logger.exception("Error extracting text from page %d", page_num)

    figure_caption_pattern = re.compile(
        r"^(?:Figure)\s+(?P<fig_label>"
        r"(?:\d+"
        r"|[A-Za-z]+\.\d+"
        r"|\(\s*[A-Za-z]+\s*\)\.\d+"
        r")"
        r")(?:\.|:)",
        re.IGNORECASE,
    )

    subfigure_pattern = re.compile(r"\(\s*[a-zA-Z]\s*\)")

    def is_subfigure_caption(txt: str) -> bool:
        return bool(subfigure_pattern.search(txt))

    result_pairs: List[Dict[str, Any]] = []

    for page_num in page_range:
        page = doc[page_num]
        page_rect = page.rect  # type: ignore[attr-defined]

        page_blocks = [b for b in text_blocks if b["page"] == page_num]
        page_blocks.sort(key=lambda b: b["bbox"].y0)

        for blk in page_blocks:
            caption_text = blk["text"]
            m = figure_caption_pattern.match(caption_text)
            if not m:
                continue

            fig_label = m.group("fig_label")
            fig_x0, fig_y0, fig_x1 = blk["bbox"][:3]

            above_blocks = []
            for ab in page_blocks:
                if ab["bbox"].y1 < fig_y0:
                    ab_height_gap = fig_y0 - ab["bbox"].y1
                    overlap_x = min(fig_x1, ab["bbox"].x1) - max(fig_x0, ab["bbox"].x0)
                    width_min = min((fig_x1 - fig_x0), (ab["bbox"].x1 - ab["bbox"].x0))
                    horiz_overlap_ratio = overlap_x / float(width_min) if width_min > 0 else 0.0

                    if (
                        len(ab["text"]) >= min_text_length
                        and not is_subfigure_caption(ab["text"])
                        and ab_height_gap >= min_vertical_gap
                        and horiz_overlap_ratio > 0.3
                    ):
                        above_blocks.append(ab)

            if above_blocks:
                above_block = max(above_blocks, key=lambda b: b["bbox"].y1)
                clip_top = above_block["bbox"].y1
            else:
                clip_top = page_rect.y0

            clip_left = fig_x0
            clip_right = fig_x1
            clip_bottom = fig_y0

            if (clip_bottom > clip_top) and (clip_right > clip_left):
                clip_rect = pymupdf.Rect(clip_left, clip_top, clip_right, clip_bottom)
                pix = page.get_pixmap(clip=clip_rect, dpi=150)  # type: ignore[attr-defined]

                fig_label_escaped = re.escape(fig_label)
                fig_hash = hashlib.md5(
                    f"figure_{fig_label_escaped}_{page_num}_{clip_rect}".encode()
                ).hexdigest()[:10]
                fig_filename = f"figure_{fig_label_escaped}_Page_{page_num + 1}_{fig_hash}.png"
                fig_filepath = img_folder_path / fig_filename
                pix.save(str(fig_filepath))

                fig_label_escaped = re.escape(fig_label)
                main_text_figure_pattern = re.compile(
                    rf"(?:Fig(?:\.|-\s*ure)?|Figure)\s*{fig_label_escaped}(?![0 - 9A-Za-z])",
                    re.IGNORECASE,
                )

                references_in_doc = []
                for tb in text_blocks:
                    if tb is blk:
                        continue
                    if main_text_figure_pattern.search(tb["text"]):
                        references_in_doc.append(tb["text"])

                result_pairs.append(
                    {
                        "img_name": f"figure_{fig_label_escaped}",
                        "caption": caption_text,
                        "images": [fig_filepath],
                        "main_text_figrefs": references_in_doc,
                    }
                )

    return result_pairs


def generate_vlm_img_cap_ref_review(
    *,
    img: Dict[str, Any],
    abstract: str,
    model: str,
    temperature: float,
    usage: TokenUsage,
) -> ImageCaptionRefReview | None:
    """Generate a VLM review for a figure with caption and references.

    Args:
        img: Dict with caption, images, main_text_figrefs
        abstract: Paper abstract
        model: Model in "provider:model" format (e.g., "anthropic:claude-sonnet-4-20250514")
        temperature: Sampling temperature
        usage: Token usage accumulator
    """
    prompt_ctx = _ImgCapRefPromptContext(
        abstract=abstract,
        caption=str(img["caption"]),
        main_text_figrefs=str(img["main_text_figrefs"]),
    )
    prompt = render_text(
        template_name="img_cap_ref_review_prompt.txt.j2",
        context=prompt_ctx._asdict(),
    )
    try:
        parsed, _ = get_structured_response_from_vlm(
            msg=prompt,
            image_paths=img["images"],
            model=model,
            system_message=_reviewer_system_prompt_base,
            temperature=temperature,
            schema_class=ImageCaptionRefReview,
            usage=usage,
        )
    except Exception:
        logger.exception("Failed to obtain structured VLM caption/reference review.")
        return None
    return ImageCaptionRefReview.model_validate(parsed.model_dump())


def generate_vlm_img_review(
    *,
    img: Dict[str, Any],
    model: str,
    temperature: float,
) -> ImageReviewResult:
    """Generate a simple VLM review for an image.

    Args:
        img: Dict with images list
        model: Model in "provider:model" format (e.g., "anthropic:claude-sonnet-4-20250514")
        temperature: Sampling temperature
    """
    usage = TokenUsage()
    prompt = render_text(template_name="img_review_prompt.txt.j2", context={})
    try:
        parsed, _ = get_structured_response_from_vlm(
            msg=prompt,
            image_paths=img["images"],
            model=model,
            system_message=_reviewer_system_prompt_base,
            temperature=temperature,
            schema_class=ImageReview,
            usage=usage,
        )
    except Exception:
        logger.exception("Failed to obtain structured VLM image review.")
        return ImageReviewResult(review=None, token_usage=usage)
    return ImageReviewResult(review=parsed.model_dump(by_alias=True), token_usage=usage)


def perform_imgs_cap_ref_review(
    *,
    model: str,
    pdf_path: Path,
    temperature: float,
    abstract: str,
) -> FigureReviewResult:
    """Review all figures in a paper with caption and reference analysis.

    Args:
        model: Model in "provider:model" format (e.g., "anthropic:claude-sonnet-4-20250514")
        pdf_path: Path to the PDF file
        temperature: Sampling temperature
        abstract: Paper abstract text
    """
    usage = TokenUsage()
    img_folder_path = pdf_path.parent / f"{pdf_path.stem}_imgs"
    img_folder_path.mkdir(parents=True, exist_ok=True)

    img_pairs = extract_figure_screenshots(pdf_path=pdf_path, img_folder_path=img_folder_path)
    img_reviews: List[FigureImageCaptionRefReview] = []

    for img in img_pairs:
        review = generate_vlm_img_cap_ref_review(
            img=img,
            abstract=abstract,
            model=model,
            temperature=temperature,
            usage=usage,
        )
        if review is not None:
            img_reviews.append(
                FigureImageCaptionRefReview(figure_name=img["img_name"], review=review)
            )

    return FigureReviewResult(reviews=img_reviews, token_usage=usage)


def detect_duplicate_figures(
    *,
    model: str,
    pdf_path: Path,
    temperature: float,
) -> DuplicateFiguresResult:
    """Detect duplicate or similar figures in a paper.

    Args:
        model: Model in "provider:model" format (e.g., "anthropic:claude-sonnet-4-20250514")
        pdf_path: Path to the PDF file
        temperature: Sampling temperature
    """
    usage = TokenUsage()
    img_folder_path = pdf_path.parent / f"{pdf_path.stem}_imgs"
    img_folder_path.mkdir(parents=True, exist_ok=True)

    img_pairs = extract_figure_screenshots(pdf_path=pdf_path, img_folder_path=img_folder_path)

    system_message = (
        "You are an expert at identifying duplicate or highly similar images. "
        "Please analyze these images and determine if they are duplicates "
        "or variations of the same visualization. "
        "Response format: reasoning, followed by "
        "`Duplicate figures: <list of duplicate figure names>`. "
        "Make sure you use the exact figure names (e.g. Figure 1, Figure 2b, etc.) "
        "as they appear in the paper. "
        "If you find no duplicates, respond with `No duplicates found`."
    )

    image_paths = [img_info["images"][0] for img_info in img_pairs]

    try:
        content, _ = get_response_from_vlm(
            msg=(
                "Are any of these images duplicates or highly similar? If so, please identify "
                "which ones are similar and explain why. "
                "Focus on content similarity, not just visual style."
            ),
            image_paths=image_paths,
            model=model,
            system_message=system_message,
            temperature=temperature,
            usage=usage,
        )
        return DuplicateFiguresResult(analysis=content, token_usage=usage)
    except Exception:
        logger.exception("Error analyzing images for duplicates")
        return DuplicateFiguresResult(
            analysis={"error": "Failed to analyze images"}, token_usage=usage
        )


def _generate_vlm_img_selection_review(
    *,
    img: Dict[str, Any],
    abstract: str,
    model: str,
    reflection_page_info: str,
    temperature: float,
    usage: TokenUsage,
) -> Dict[str, Any] | None:
    selection_ctx = _ImgCapSelectionPromptContext(
        abstract=abstract,
        caption=str(img["caption"]),
        main_text_figrefs=str(img["main_text_figrefs"]),
        reflection_page_info=reflection_page_info,
    )
    prompt = render_text(
        template_name="img_cap_selection_prompt.txt.j2",
        context=selection_ctx._asdict(),
    )
    try:
        parsed, _ = get_structured_response_from_vlm(
            msg=prompt,
            image_paths=img["images"],
            model=model,
            system_message=_reviewer_system_prompt_base,
            temperature=temperature,
            schema_class=ImageSelectionReview,
            usage=usage,
        )
    except Exception:
        logger.exception("Failed to obtain structured VLM selection review.")
        return None
    return parsed.model_dump(by_alias=True)


def perform_imgs_cap_ref_review_selection(
    *,
    model: str,
    pdf_path: Path,
    reflection_page_info: str,
    temperature: float,
    abstract: str,
) -> FigureSelectionReviewResult:
    """Review figures for selection decisions.

    Args:
        model: Model in "provider:model" format (e.g., "anthropic:claude-sonnet-4-20250514")
        pdf_path: Path to the PDF file
        reflection_page_info: Page limit information
        temperature: Sampling temperature
        abstract: Paper abstract text
    """
    usage = TokenUsage()
    img_folder_path = pdf_path.parent / f"{pdf_path.stem}_imgs"
    img_folder_path.mkdir(parents=True, exist_ok=True)

    img_pairs = extract_figure_screenshots(pdf_path=pdf_path, img_folder_path=img_folder_path)
    img_reviews: Dict[str, Any] = {}

    for img in img_pairs:
        review = _generate_vlm_img_selection_review(
            img=img,
            abstract=abstract,
            model=model,
            reflection_page_info=reflection_page_info,
            temperature=temperature,
            usage=usage,
        )
        img_reviews[img["img_name"]] = review

    return FigureSelectionReviewResult(reviews=img_reviews, token_usage=usage)
