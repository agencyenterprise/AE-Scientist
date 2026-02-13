"""
S3 service for handling PDF uploads and downloads.

Simplified version for AE Paper Review (PDF-only).
"""

import logging
import unicodedata

import boto3
import magic
import requests
from botocore.exceptions import ClientError, NoCredentialsError

from app.config import settings

logger = logging.getLogger(__name__)


class S3Service:
    """Service for handling S3 file operations."""

    # Only allow PDF for paper reviews
    ALLOWED_MIME_TYPES = {
        "application/pdf",
    }

    # Maximum file size (20MB in bytes for PDFs)
    MAX_FILE_SIZE = 20 * 1024 * 1024

    def __init__(self) -> None:
        """Initialize S3 service with AWS credentials from settings."""
        self.aws_access_key_id = settings.aws.access_key_id
        self.aws_secret_access_key = settings.aws.secret_access_key
        self.aws_region = settings.aws.region
        self.bucket_name = settings.aws.s3_bucket_name

        try:
            self.s3_client = boto3.client(
                "s3",
                aws_access_key_id=self.aws_access_key_id,
                aws_secret_access_key=self.aws_secret_access_key,
                region_name=self.aws_region,
            )
            logger.debug("S3 service initialized for bucket: %s", self.bucket_name)
        except NoCredentialsError as e:
            logger.error("AWS credentials not found: %s", e)
            raise ValueError("Invalid AWS credentials") from e

    def validate_file_type(self, file_content: bytes) -> str:
        """
        Validate file type using magic number detection.

        Args:
            file_content: File content as bytes

        Returns:
            MIME type string if valid

        Raises:
            ValueError: If file type is not allowed or cannot be determined
        """
        try:
            # Use python-magic to detect MIME type from file content
            mime_type = magic.from_buffer(file_content, mime=True)
            logger.debug("Detected MIME type: %s", mime_type)

            if mime_type not in self.ALLOWED_MIME_TYPES:
                raise ValueError(
                    f"File type '{mime_type}' is not allowed. "
                    f"Allowed types: {', '.join(sorted(self.ALLOWED_MIME_TYPES))}"
                )

            return mime_type

        except Exception as e:
            logger.error("File type validation failed: %s", e)
            raise ValueError(f"Could not determine file type: {e}") from e

    def validate_file_size(self, file_content: bytes) -> None:
        """
        Validate file size.

        Args:
            file_content: File content as bytes

        Raises:
            ValueError: If file size exceeds maximum allowed size
        """
        file_size = len(file_content)
        if file_size > self.MAX_FILE_SIZE:
            raise ValueError(
                f"File size ({file_size} bytes) exceeds maximum allowed size "
                f"({self.MAX_FILE_SIZE} bytes / {self.MAX_FILE_SIZE // 1024 // 1024}MB)"
            )

    def _sanitize_ascii(self, value: str) -> str:
        """Return an ASCII-only representation of value suitable for S3 metadata.

        - First try fast-path ASCII encode
        - Fallback: Unicode NFKD normalize and drop non-ASCII diacritics
        """
        try:
            value.encode("ascii")
            return value
        except Exception:
            normalized = unicodedata.normalize("NFKD", value)
            ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
            return ascii_only

    def upload_pdf(
        self,
        file_content: bytes,
        s3_key: str,
        original_filename: str,
        user_id: int,
    ) -> None:
        """
        Upload a PDF file to S3.

        Args:
            file_content: PDF file content as bytes
            s3_key: S3 key for the file
            original_filename: Original filename
            user_id: ID of the user uploading

        Raises:
            ValueError: If file validation fails
            Exception: If S3 upload fails
        """
        # Validate file size
        self.validate_file_size(file_content)

        # Validate file type
        self.validate_file_type(file_content)

        try:
            # Upload file to S3
            metadata = {
                "original_filename": original_filename[:255],  # S3 metadata limit
                "user_id": str(user_id),
            }
            sanitized_metadata = {
                key: self._sanitize_ascii(value) for key, value in metadata.items()
            }
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=file_content,
                ContentType="application/pdf",
                Metadata=sanitized_metadata,
            )

            logger.debug("PDF uploaded successfully: %s", s3_key)

        except ClientError as e:
            logger.error("S3 upload failed: %s", e)
            raise Exception(f"Failed to upload file: {e}") from e

    def generate_download_url(self, s3_key: str, expires_in: int) -> str:
        """
        Generate a temporary signed URL for downloading a file.

        Args:
            s3_key: S3 key for the file
            expires_in: URL expiration time in seconds

        Returns:
            Temporary signed URL for file download

        Raises:
            Exception: If URL generation fails
        """
        try:
            url = self.s3_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket_name, "Key": s3_key},
                ExpiresIn=expires_in,
            )

            logger.debug("Generated download URL for: %s", s3_key)
            return str(url)

        except ClientError as e:
            logger.error("Failed to generate download URL: %s", e)
            raise Exception(f"Failed to generate download URL: {e}") from e

    def download_file_content(self, s3_key: str) -> bytes:
        """
        Download file content from S3 using the s3_key.

        Args:
            s3_key: S3 key (path) of the file to download

        Returns:
            File content as bytes

        Raises:
            Exception: If download fails
        """
        try:
            # Generate temporary download URL
            download_url = self.generate_download_url(s3_key=s3_key, expires_in=3600)

            # Download file content
            response = requests.get(download_url, timeout=30)
            response.raise_for_status()

            logger.debug("Successfully downloaded file content for s3_key: %s", s3_key)
            return response.content

        except Exception as e:
            logger.error("Failed to download file content for s3_key %s: %s", s3_key, e)
            raise Exception(f"Failed to download file content: {e}") from e

    def file_exists(self, s3_key: str) -> bool:
        """
        Check if a file exists in S3.

        Args:
            s3_key: S3 key for the file

        Returns:
            True if file exists, False otherwise
        """
        try:
            self.s3_client.head_object(Bucket=self.bucket_name, Key=s3_key)
            return True
        except ClientError:
            return False


# Global instance
_s3_service: S3Service | None = None


def get_s3_service() -> S3Service:
    """Get the global S3 service instance."""
    global _s3_service
    if _s3_service is None:
        _s3_service = S3Service()
    return _s3_service
