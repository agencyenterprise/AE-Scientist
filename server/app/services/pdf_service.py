"""
PDF text extraction service.

This module provides functionality to extract text content from PDF files
for use in LLM context processing.
"""

import io
import logging

import pdfplumber

logger = logging.getLogger(__name__)


class PDFService:
    """Service for extracting text from PDF files."""

    @staticmethod
    def extract_text_from_pdf(file_content: bytes) -> str:
        """
        Extract text content from a PDF file.

        Args:
            file_content: PDF file content as bytes

        Returns:
            Extracted text content as string

        Raises:
            ValueError: If PDF processing fails or text extraction is empty
            Exception: If unexpected error occurs during processing
        """
        try:
            # Create a file-like object from bytes
            pdf_buffer = io.BytesIO(file_content)

            extracted_text = ""
            page_count = 0

            # Use pdfplumber to extract text
            with pdfplumber.open(pdf_buffer) as pdf:
                logger.debug(f"PDF opened successfully, {len(pdf.pages)} pages found")

                for page_num, page in enumerate(pdf.pages, 1):
                    try:
                        page_text = page.extract_text()
                        if page_text:
                            extracted_text += f"\n--- Page {page_num} ---\n"
                            extracted_text += page_text + "\n"
                            page_count += 1
                        else:
                            logger.warning(f"No text found on page {page_num}")
                    except Exception as page_error:
                        logger.warning(f"Failed to extract text from page {page_num}: {page_error}")
                        continue

            # Clean up the extracted text
            extracted_text = extracted_text.strip()

            if not extracted_text:
                raise ValueError("No text content could be extracted from the PDF")

            logger.info(
                f"Successfully extracted text from {page_count} pages ({len(extracted_text)} characters)"
            )
            return extracted_text

        except ValueError:
            # Re-raise ValueError as-is
            raise
        except Exception as e:
            logger.error(f"PDF text extraction failed: {e}")
            raise Exception(f"Failed to extract text from PDF: {str(e)}") from e
