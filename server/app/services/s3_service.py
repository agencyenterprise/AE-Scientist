"""
S3 service for handling file uploads and downloads.

This module provides S3 integration for storing and retrieving file attachments
with proper validation and secure access via temporary signed URLs.
"""

import logging
import os
import unicodedata
from urllib.parse import quote

import boto3
import magic
import requests
from botocore.exceptions import ClientError, NoCredentialsError

logger = logging.getLogger(__name__)


class S3Service:
    """Service for handling S3 file operations."""

    # Allowed file types with their MIME types
    ALLOWED_MIME_TYPES = {
        # Images
        "image/jpeg",
        "image/jpg",
        "image/png",
        "image/gif",
        "image/webp",
        "image/svg+xml",
        # Documents
        "application/pdf",
        "text/plain",
    }

    # Maximum file size (10MB in bytes)
    MAX_FILE_SIZE = 10 * 1024 * 1024

    def __init__(self) -> None:
        """Initialize S3 service with AWS credentials."""
        self.aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID")
        self.aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY")
        self.aws_region = os.getenv("AWS_REGION")
        self.bucket_name = os.getenv("AWS_S3_BUCKET_NAME")

        if not all(
            [self.aws_access_key_id, self.aws_secret_access_key, self.aws_region, self.bucket_name]
        ):
            raise ValueError(
                "Missing required AWS configuration. Please set AWS_ACCESS_KEY_ID, "
                "AWS_SECRET_ACCESS_KEY, AWS_REGION, and AWS_S3_BUCKET_NAME environment variables."
            )

        try:
            self.s3_client = boto3.client(
                "s3",
                aws_access_key_id=self.aws_access_key_id,
                aws_secret_access_key=self.aws_secret_access_key,
                region_name=self.aws_region,
            )
            logger.info(f"S3 service initialized for bucket: {self.bucket_name}")
        except NoCredentialsError as e:
            logger.error(f"AWS credentials not found: {e}")
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
            logger.debug(f"Detected MIME type: {mime_type}")

            if mime_type not in self.ALLOWED_MIME_TYPES:
                raise ValueError(
                    f"File type '{mime_type}' is not allowed. "
                    f"Allowed types: {', '.join(sorted(self.ALLOWED_MIME_TYPES))}"
                )

            return mime_type

        except Exception as e:
            logger.error(f"File type validation failed: {e}")
            raise ValueError(f"Could not determine file type: {str(e)}") from e

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

    def upload_file(
        self, file_content: bytes, conversation_id: int, filename: str, file_type: str
    ) -> str:
        """
        Upload file to S3 and return the S3 key.

        Args:
            file_content: File content as bytes
            conversation_id: ID of the conversation
            filename: Original filename
            file_type: MIME type of the file

        Returns:
            S3 key for the uploaded file

        Raises:
            ValueError: If file validation fails
            Exception: If S3 upload fails
        """
        # Validate file size
        self.validate_file_size(file_content)

        # Validate file type
        detected_mime_type = self.validate_file_type(file_content)

        # Use detected MIME type instead of provided one for security
        file_type = detected_mime_type

        # Generate S3 key with conversation folder structure
        # URL-encode filename to handle special characters
        safe_filename = quote(filename, safe="")
        s3_key = f"conversations/{conversation_id}/files/{safe_filename}"

        try:
            # Upload file to S3
            metadata = {
                "original_filename": filename,
                "conversation_id": str(conversation_id),
                "file_size": str(len(file_content)),
            }
            # S3 metadata values must be ASCII-only; sanitize non-ASCII safely
            sanitized_metadata = {
                key: self._sanitize_ascii(value) for key, value in metadata.items()
            }
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=file_content,
                ContentType=file_type,
                Metadata=sanitized_metadata,
            )

            logger.info(f"File uploaded successfully: {s3_key}")
            return s3_key

        except ClientError as e:
            logger.error(f"S3 upload failed: {e}")
            raise Exception(f"Failed to upload file: {str(e)}") from e

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

    def generate_download_url(self, s3_key: str, expires_in: int = 3600) -> str:
        """
        Generate a temporary signed URL for downloading a file.

        Args:
            s3_key: S3 key for the file
            expires_in: URL expiration time in seconds (default: 1 hour)

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

            logger.debug(f"Generated download URL for: {s3_key}")
            return str(url)

        except ClientError as e:
            logger.error(f"Failed to generate download URL: {e}")
            raise Exception(f"Failed to generate download URL: {str(e)}") from e

    def delete_file(self, s3_key: str) -> None:
        """
        Delete a file from S3.

        Args:
            s3_key: S3 key for the file to delete

        Raises:
            Exception: If deletion fails
        """
        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=s3_key)
            logger.info(f"File deleted successfully: {s3_key}")

        except ClientError as e:
            logger.error(f"S3 deletion failed: {e}")
            raise Exception(f"Failed to delete file: {str(e)}") from e

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

    def get_file_info(self, s3_key: str) -> dict:
        """
        Get file metadata from S3.

        Args:
            s3_key: S3 key for the file

        Returns:
            Dictionary containing file metadata

        Raises:
            Exception: If file not found or metadata retrieval fails
        """
        try:
            response = self.s3_client.head_object(Bucket=self.bucket_name, Key=s3_key)

            return {
                "content_type": response.get("ContentType", ""),
                "content_length": response.get("ContentLength", 0),
                "last_modified": response.get("LastModified"),
                "metadata": response.get("Metadata", {}),
            }

        except ClientError as e:
            logger.error(f"Failed to get file info: {e}")
            raise Exception(f"Failed to get file info: {str(e)}") from e

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
            download_url = self.generate_download_url(s3_key)

            # Download file content
            response = requests.get(download_url, timeout=30)
            response.raise_for_status()

            logger.debug(f"Successfully downloaded file content for s3_key: {s3_key}")
            return response.content

        except Exception as e:
            logger.error(f"Failed to download file content for s3_key {s3_key}: {e}")
            raise Exception(f"Failed to download file content: {str(e)}") from e


# Global instance
_s3_service = None


def get_s3_service() -> S3Service:
    """Get the global S3 service instance."""
    global _s3_service
    if _s3_service is None:
        _s3_service = S3Service()
    return _s3_service
