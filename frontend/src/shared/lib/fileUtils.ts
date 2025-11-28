/**
 * File validation and utility functions for file uploads.
 *
 * Provides client-side validation for file types, sizes, and icons
 * to match backend validation rules.
 */

// File size constants
export const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB in bytes

// Allowed file types (matches backend validation)
export const ALLOWED_FILE_TYPES = {
  // Images
  "image/jpeg": [".jpg", ".jpeg"],
  "image/png": [".png"],
  "image/gif": [".gif"],
  "image/webp": [".webp"],
  "image/svg+xml": [".svg"],
  // Documents
  "application/pdf": [".pdf"],
  "text/plain": [".txt", ".md", ".csv"],
} as const;

// Get all allowed extensions
export const ALLOWED_EXTENSIONS = Object.values(ALLOWED_FILE_TYPES).flat();

/**
 * Validate file type based on MIME type and extension.
 */
export function validateFileType(file: File): { isValid: boolean; error?: string } {
  const mimeType = file.type;
  const extension = getFileExtension(file.name).toLowerCase();

  // Check if MIME type is allowed
  if (!Object.keys(ALLOWED_FILE_TYPES).includes(mimeType)) {
    return {
      isValid: false,
      error: `File type "${mimeType}" is not allowed. Allowed types: images (JPEG, PNG, GIF, WebP, SVG) and PDF documents.`,
    };
  }

  // Check if extension matches MIME type
  const allowedExtensions = ALLOWED_FILE_TYPES[mimeType as keyof typeof ALLOWED_FILE_TYPES];
  if (!allowedExtensions || !(allowedExtensions as readonly string[]).includes(extension)) {
    return {
      isValid: false,
      error: `File extension "${extension}" does not match MIME type "${mimeType}".`,
    };
  }

  return { isValid: true };
}

/**
 * Validate file size.
 */
export function validateFileSize(file: File): { isValid: boolean; error?: string } {
  if (file.size > MAX_FILE_SIZE) {
    const maxSizeMB = MAX_FILE_SIZE / (1024 * 1024);
    const fileSizeMB = (file.size / (1024 * 1024)).toFixed(2);
    return {
      isValid: false,
      error: `File size (${fileSizeMB}MB) exceeds maximum allowed size (${maxSizeMB}MB).`,
    };
  }

  return { isValid: true };
}

/**
 * Validate a file completely (type and size).
 */
export function validateFile(file: File): { isValid: boolean; errors: string[] } {
  const errors: string[] = [];

  const typeValidation = validateFileType(file);
  if (!typeValidation.isValid && typeValidation.error) {
    errors.push(typeValidation.error);
  }

  const sizeValidation = validateFileSize(file);
  if (!sizeValidation.isValid && sizeValidation.error) {
    errors.push(sizeValidation.error);
  }

  return {
    isValid: errors.length === 0,
    errors,
  };
}

/**
 * Get file extension from filename.
 */
export function getFileExtension(filename: string): string {
  const lastDot = filename.lastIndexOf(".");
  return lastDot === -1 ? "" : filename.substring(lastDot);
}

/**
 * Get file icon based on file type.
 */
export function getFileIcon(mimeType: string): string {
  if (mimeType.startsWith("image/")) {
    return "🖼️";
  }

  switch (mimeType) {
    case "application/pdf":
      return "📄";
    case "text/plain":
      return "📝";
    default:
      return "📎";
  }
}

/**
 * Format file size in human-readable format.
 */
export function formatFileSize(bytes: number): string {
  if (bytes === 0) return "0 Bytes";

  const k = 1024;
  const sizes = ["Bytes", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));

  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(2))} ${sizes[i]}`;
}

/**
 * Check if file type is an image.
 */
export function isImageFile(mimeType: string): boolean {
  return mimeType.startsWith("image/");
}

/**
 * Check if file type is a PDF.
 */
export function isPdfFile(mimeType: string): boolean {
  return mimeType === "application/pdf";
}

/**
 * Get file display name (truncate if too long).
 */
export function getDisplayFileName(filename: string, maxLength: number = 30): string {
  if (filename.length <= maxLength) {
    return filename;
  }

  const extension = getFileExtension(filename);
  const nameWithoutExt = filename.substring(0, filename.length - extension.length);
  const maxNameLength = maxLength - extension.length - 3; // 3 for "..."

  if (maxNameLength <= 0) {
    return `...${extension}`;
  }

  return `${nameWithoutExt.substring(0, maxNameLength)}...${extension}`;
}

/**
 * Create a preview URL for image files.
 */
export function createImagePreview(file: File): string {
  if (!isImageFile(file.type)) {
    throw new Error("File is not an image");
  }
  return URL.createObjectURL(file);
}

/**
 * Cleanup preview URL (should be called when component unmounts).
 */
export function cleanupPreviewUrl(url: string): void {
  URL.revokeObjectURL(url);
}

/**
 * Generate unique upload ID for tracking uploads.
 */
export function generateUploadId(): string {
  return `upload_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;
}

/**
 * Check if drag event contains files.
 */
export function hasFiles(event: DragEvent): boolean {
  return Boolean(
    event.dataTransfer &&
      event.dataTransfer.types &&
      Array.from(event.dataTransfer.types).includes("Files")
  );
}

/**
 * Get files from drag event.
 */
export function getFilesFromDragEvent(event: DragEvent): File[] {
  const files: File[] = [];

  if (event.dataTransfer) {
    if (event.dataTransfer.items) {
      // Use DataTransferItemList interface
      for (let i = 0; i < event.dataTransfer.items.length; i++) {
        const item = event.dataTransfer.items[i];
        if (item && item.kind === "file") {
          const file = item.getAsFile();
          if (file) {
            files.push(file);
          }
        }
      }
    } else {
      // Use DataTransfer interface
      for (let i = 0; i < event.dataTransfer.files.length; i++) {
        const file = event.dataTransfer.files[i];
        if (file) {
          files.push(file);
        }
      }
    }
  }

  return files;
}
