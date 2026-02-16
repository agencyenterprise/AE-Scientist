"""PDF loading utilities for paper review."""

import logging

import pymupdf
from pypdf import PdfReader

logger = logging.getLogger(__name__)


def load_paper(pdf_path: str, num_pages: int | None = None, min_size: int = 100) -> str:
    """Load paper text from a PDF file.

    Args:
        pdf_path: Path to the PDF file
        num_pages: Optional limit on number of pages to extract
        min_size: Minimum text size to consider valid

    Returns:
        Extracted text from the PDF
    """
    try:
        # Lazy import with stdout suppression to avoid polluting output
        import io
        import sys

        _original_stdout = sys.stdout
        sys.stdout = io.StringIO()
        import pymupdf4llm  # type: ignore[import-untyped]

        sys.stdout = _original_stdout

        text: str
        if num_pages is None:
            text = str(pymupdf4llm.to_markdown(pdf_path))
        else:
            reader = PdfReader(pdf_path)
            min_pages = min(len(reader.pages), num_pages)
            text = str(pymupdf4llm.to_markdown(pdf_path, pages=list(range(min_pages))))
        if len(text) < min_size:
            raise Exception("Text too short")
    except Exception as e:
        logger.warning(f"Error with pymupdf4llm, falling back to pymupdf: {e}")
        try:
            doc = pymupdf.open(pdf_path)
            page_limit = num_pages if num_pages else len(doc)
            text = ""
            for i in range(min(page_limit, len(doc))):
                page = doc[i]
                text += str(page.get_text())  # type: ignore[attr-defined]
            if len(text) < min_size:
                raise Exception("Text too short")
        except Exception as e:
            logger.warning(f"Error with pymupdf, falling back to pypdf: {e}")
            reader = PdfReader(pdf_path)
            if num_pages is None:
                pages = reader.pages
            else:
                pages = reader.pages[:num_pages]
            text = "".join(page.extract_text() for page in pages)
            if len(text) < min_size:
                raise Exception("Text too short")
    return text
