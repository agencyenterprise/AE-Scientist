"""VLM-based figure review functionality."""

import hashlib
import logging
import os
import re
from typing import Any, Dict, List, NamedTuple, Optional

import pymupdf  # type: ignore[import-untyped]

from .llm.token_tracking import TokenUsage
from .llm.vlm import get_response_from_vlm, get_structured_response_from_vlm
from .llm_review import load_paper
from .models import (
    FigureImageCaptionRefReview,
    ImageCaptionRefReview,
    ImageReview,
    ImageSelectionReview,
)
from .prompts import render_text

logger = logging.getLogger(__name__)


# Pre-render static templates
_reviewer_system_prompt_base = render_text(
    template_name="vlm/reviewer_system_prompt_base.txt.j2",
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
    pdf_path: str,
    img_folder_path: str,
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
    os.makedirs(img_folder_path, exist_ok=True)
    doc = pymupdf.open(pdf_path)
    page_range = range(len(doc)) if num_pages is None else range(min(num_pages, len(doc)))

    # Extract all text blocks from the document
    text_blocks: List[Dict[str, Any]] = []
    for page_num in page_range:
        page = doc[page_num]
        try:
            blocks = page.get_text("blocks")
            for b in blocks:
                txt = b[4].strip()
                if txt:
                    bbox = pymupdf.Rect(b[0], b[1], b[2], b[3])
                    text_blocks.append({"page": page_num, "bbox": bbox, "text": txt})
        except Exception as e:
            logger.exception(f"Error extracting text from page {page_num}: {e}")

    # Regex for figure captions
    figure_caption_pattern = re.compile(
        r"^(?:Figure)\s+(?P<fig_label>"
        r"(?:\d+"
        r"|[A-Za-z]+\.\d+"
        r"|\(\s*[A-Za-z]+\s*\)\.\d+"
        r")"
        r")(?:\.|:)",
        re.IGNORECASE,
    )

    # Detect sub-figure captions
    subfigure_pattern = re.compile(r"\(\s*[a-zA-Z]\s*\)")

    def is_subfigure_caption(txt: str) -> bool:
        return bool(subfigure_pattern.search(txt))

    result_pairs: List[Dict[str, Any]] = []

    for page_num in page_range:
        page = doc[page_num]
        page_rect = page.rect

        page_blocks = [b for b in text_blocks if b["page"] == page_num]
        page_blocks.sort(key=lambda b: b["bbox"].y0)

        for blk in page_blocks:
            caption_text = blk["text"]
            m = figure_caption_pattern.match(caption_text)
            if not m:
                continue

            fig_label = m.group("fig_label")
            fig_x0, fig_y0, fig_x1, fig_y1 = blk["bbox"]

            # Find a large text block above the caption
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
                pix = page.get_pixmap(clip=clip_rect, dpi=150)

                fig_label_escaped = re.escape(fig_label)
                fig_hash = hashlib.md5(
                    f"figure_{fig_label_escaped}_{page_num}_{clip_rect}".encode()
                ).hexdigest()[:10]
                fig_filename = f"figure_{fig_label_escaped}_Page_{page_num + 1}_{fig_hash}.png"
                fig_filepath = os.path.join(img_folder_path, fig_filename)
                pix.save(fig_filepath)

                # Find references across the entire document
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


def extract_abstract(text: str) -> str:
    """Extract abstract from paper text.

    Args:
        text: Full paper text in markdown format

    Returns:
        Extracted abstract text or empty string if not found
    """
    lines = text.split("\n")
    heading_pattern = re.compile(r"^\s*#+\s*(.*)$")

    abstract_start = None
    for i, line in enumerate(lines):
        match = heading_pattern.match(line)
        if match:
            heading_text = match.group(1)
            if "abstract" in heading_text.lower():
                abstract_start = i
                break

    if abstract_start is None:
        return ""

    abstract_lines = []
    for j in range(abstract_start + 1, len(lines)):
        if heading_pattern.match(lines[j]):
            break
        abstract_lines.append(lines[j])

    return "\n".join(abstract_lines).strip()


def generate_vlm_img_cap_ref_review(
    img: Dict[str, Any],
    abstract: str,
    provider: str,
    model: str,
    temperature: float,
    usage: TokenUsage | None = None,
) -> ImageCaptionRefReview | None:
    """Generate a VLM review for a figure with caption and references.

    Args:
        img: Dict with caption, images, main_text_figrefs
        abstract: Paper abstract
        provider: VLM provider (e.g., "anthropic", "openai")
        model: Model name (e.g., "claude-sonnet-4-20250514")
        temperature: Sampling temperature
        usage: Optional token usage accumulator

    Returns:
        ImageCaptionRefReview or None if failed
    """
    prompt_ctx = _ImgCapRefPromptContext(
        abstract=abstract,
        caption=str(img["caption"]),
        main_text_figrefs=str(img["main_text_figrefs"]),
    )
    prompt = render_text(
        template_name="vlm/img_cap_ref_review_prompt.txt.j2",
        context=prompt_ctx._asdict(),
    )
    try:
        parsed, _ = get_structured_response_from_vlm(
            msg=prompt,
            image_paths=img["images"],
            provider=provider,
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
    img: Dict[str, Any],
    provider: str,
    model: str,
    temperature: float,
    usage: TokenUsage | None = None,
) -> Dict[str, Any] | None:
    """Generate a simple VLM review for an image.

    Args:
        img: Dict with images list
        provider: VLM provider (e.g., "anthropic", "openai")
        model: Model name (e.g., "claude-sonnet-4-20250514")
        temperature: Sampling temperature
        usage: Optional token usage accumulator

    Returns:
        Review dict or None if failed
    """
    prompt = render_text(template_name="vlm/img_review_prompt.txt.j2", context={})
    try:
        parsed, _ = get_structured_response_from_vlm(
            msg=prompt,
            image_paths=img["images"],
            provider=provider,
            model=model,
            system_message=_reviewer_system_prompt_base,
            temperature=temperature,
            schema_class=ImageReview,
            usage=usage,
        )
    except Exception:
        logger.exception("Failed to obtain structured VLM image review.")
        return None
    return parsed.model_dump(by_alias=True)


def perform_imgs_cap_ref_review(
    provider: str,
    model: str,
    pdf_path: str,
    temperature: float,
    usage: TokenUsage | None = None,
) -> List[FigureImageCaptionRefReview]:
    """Review all figures in a paper with caption and reference analysis.

    Args:
        provider: VLM provider (e.g., "anthropic", "openai")
        model: Model name (e.g., "claude-sonnet-4-20250514")
        pdf_path: Path to the PDF file
        temperature: Sampling temperature
        usage: Optional token usage accumulator

    Returns:
        List of FigureImageCaptionRefReview for each figure
    """
    paper_txt = load_paper(pdf_path)
    img_folder_path = os.path.join(
        os.path.dirname(pdf_path),
        f"{os.path.splitext(os.path.basename(pdf_path))[0]}_imgs",
    )
    if not os.path.exists(img_folder_path):
        os.makedirs(img_folder_path)

    img_pairs = extract_figure_screenshots(pdf_path, img_folder_path)
    img_reviews: List[FigureImageCaptionRefReview] = []
    abstract = extract_abstract(paper_txt)

    for img in img_pairs:
        review = generate_vlm_img_cap_ref_review(
            img=img,
            abstract=abstract,
            provider=provider,
            model=model,
            temperature=temperature,
            usage=usage,
        )
        if review is not None:
            img_reviews.append(
                FigureImageCaptionRefReview(figure_name=img["img_name"], review=review)
            )

    return img_reviews


def detect_duplicate_figures(
    provider: str,
    model: str,
    pdf_path: str,
    temperature: float,
    usage: TokenUsage | None = None,
) -> str | Dict[str, str]:
    """Detect duplicate or similar figures in a paper.

    Args:
        provider: VLM provider (e.g., "anthropic", "openai")
        model: Model name (e.g., "claude-sonnet-4-20250514")
        pdf_path: Path to the PDF file
        temperature: Sampling temperature
        usage: Optional token usage accumulator

    Returns:
        Analysis string or error dict
    """
    load_paper(pdf_path)
    img_folder_path = os.path.join(
        os.path.dirname(pdf_path),
        f"{os.path.splitext(os.path.basename(pdf_path))[0]}_imgs",
    )
    if not os.path.exists(img_folder_path):
        os.makedirs(img_folder_path)

    img_pairs = extract_figure_screenshots(pdf_path, img_folder_path)

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
            provider=provider,
            model=model,
            system_message=system_message,
            temperature=temperature,
            usage=usage,
        )
        return content
    except Exception as e:
        logger.exception(f"Error analyzing images: {e}")
        return {"error": str(e)}


def generate_vlm_img_selection_review(
    img: Dict[str, Any],
    abstract: str,
    provider: str,
    model: str,
    reflection_page_info: str,
    temperature: float,
    usage: TokenUsage | None = None,
) -> Dict[str, Any] | None:
    """Generate a VLM review for figure selection decisions.

    Args:
        img: Dict with caption, images, main_text_figrefs
        abstract: Paper abstract
        provider: VLM provider (e.g., "anthropic", "openai")
        model: Model name (e.g., "claude-sonnet-4-20250514")
        reflection_page_info: Page limit information
        temperature: Sampling temperature
        usage: Optional token usage accumulator

    Returns:
        Review dict or None if failed
    """
    selection_ctx = _ImgCapSelectionPromptContext(
        abstract=abstract,
        caption=str(img["caption"]),
        main_text_figrefs=str(img["main_text_figrefs"]),
        reflection_page_info=reflection_page_info,
    )
    prompt = render_text(
        template_name="vlm/img_cap_selection_prompt.txt.j2",
        context=selection_ctx._asdict(),
    )
    try:
        parsed, _ = get_structured_response_from_vlm(
            msg=prompt,
            image_paths=img["images"],
            provider=provider,
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
    provider: str,
    model: str,
    pdf_path: str,
    reflection_page_info: str,
    temperature: float,
    usage: TokenUsage | None = None,
) -> Dict[str, Any]:
    """Review figures for selection decisions.

    Args:
        provider: VLM provider (e.g., "anthropic", "openai")
        model: Model name (e.g., "claude-sonnet-4-20250514")
        pdf_path: Path to the PDF file
        reflection_page_info: Page limit information
        temperature: Sampling temperature
        usage: Optional token usage accumulator

    Returns:
        Dict mapping figure names to reviews
    """
    paper_txt = load_paper(pdf_path)
    img_folder_path = os.path.join(
        os.path.dirname(pdf_path),
        f"{os.path.splitext(os.path.basename(pdf_path))[0]}_imgs",
    )
    if not os.path.exists(img_folder_path):
        os.makedirs(img_folder_path)

    img_pairs = extract_figure_screenshots(pdf_path, img_folder_path)
    img_reviews: Dict[str, Any] = {}
    abstract = extract_abstract(paper_txt)

    for img in img_pairs:
        review = generate_vlm_img_selection_review(
            img=img,
            abstract=abstract,
            provider=provider,
            model=model,
            reflection_page_info=reflection_page_info,
            temperature=temperature,
            usage=usage,
        )
        img_reviews[img["img_name"]] = review

    return img_reviews
