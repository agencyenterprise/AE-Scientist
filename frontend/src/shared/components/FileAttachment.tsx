"use client";

import { useEffect, useState } from "react";
import Image from "next/image";

import { config } from "@/shared/lib/config";
import {
  formatFileSize,
  getDisplayFileName,
  getFileIcon,
  isImageFile,
} from "@/shared/lib/fileUtils";
import type { FileAttachment as FileAttachmentType } from "@/types";

interface FileAttachmentProps {
  attachment: FileAttachmentType;
  showPreview?: boolean;
  className?: string;
}

export function FileAttachment({
  attachment,
  showPreview = true,
  className = "",
}: FileAttachmentProps) {
  const [isDownloading, setIsDownloading] = useState(false);
  const [downloadError, setDownloadError] = useState<string | null>(null);
  const [imageError, setImageError] = useState(false);
  const [showImageModal, setShowImageModal] = useState(false);

  // Handle ESC key to close modal
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape" && showImageModal) {
        setShowImageModal(false);
      }
    };

    if (showImageModal) {
      document.addEventListener("keydown", handleKeyDown);
      // Prevent body scroll when modal is open
      document.body.style.overflow = "hidden";
    }

    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      document.body.style.overflow = "unset";
    };
  }, [showImageModal]);

  const handleDownload = () => {
    if (isDownloading) return;

    setIsDownloading(true);
    setDownloadError(null);

    try {
      // Create a direct link to the backend endpoint, letting the browser handle the redirect
      const link = document.createElement("a");
      link.href = `${config.apiUrl}/conversations/files/${attachment.id}/download`;
      link.download = attachment.filename;
      link.target = "_blank";
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    } catch (error) {
      // eslint-disable-next-line no-console
      console.error("Download error:", error);
      setDownloadError(error instanceof Error ? error.message : "Download failed");
    } finally {
      setIsDownloading(false);
    }
  };

  const formatDate = (dateString: string): string => {
    const date = new Date(dateString);
    return date.toLocaleDateString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  const isImage = isImageFile(attachment.file_type);
  const fileIcon = getFileIcon(attachment.file_type);
  const formattedSize = formatFileSize(attachment.file_size);

  return (
    <div
      className={`inline-block max-w-xs bg-card border border-border rounded-lg overflow-hidden shadow-sm ${className}`}
    >
      {/* Image Preview */}
      {isImage && showPreview && !imageError && (
        <div className="relative">
          <Image
            src={`${config.apiUrl}/conversations/files/${attachment.id}/download`}
            alt={attachment.filename}
            width={320}
            height={128}
            className="w-full h-32 object-contain bg-muted cursor-pointer hover:opacity-90 transition-opacity"
            onError={() => setImageError(true)}
            onClick={() => setShowImageModal(true)}
            loading="lazy"
            title="Click to view full size"
            unoptimized
          />
          {/* Click indicator */}
          <div
            className="absolute inset-0 flex items-center justify-center opacity-0 hover:opacity-100 transition-opacity bg-black bg-opacity-20 cursor-pointer"
            onClick={() => setShowImageModal(true)}
            title="Click to view full size"
          >
            <svg
              className="w-6 h-6 text-white"
              fill="none"
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0zM10 7v3m0 0v3m0-3h3m-3 0H7" />
            </svg>
          </div>
        </div>
      )}

      {/* Compact File Info */}
      <div className="p-2">
        {/* File Icon for non-images */}
        {(!isImage || !showPreview || imageError) && (
          <div className="flex justify-center mb-2">
            <div className="w-8 h-8 flex items-center justify-center bg-muted rounded text-lg">
              {fileIcon}
            </div>
          </div>
        )}

        {/* Metadata and Actions Row */}
        <div className="flex items-center justify-between">
          {/* Left side: File size and type */}
          <div className="flex items-center space-x-2">
            <span className="text-xs text-muted-foreground">{formattedSize}</span>
            <span className="inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium bg-muted text-foreground">
              {attachment.file_type.split("/")[1]?.toUpperCase() || "FILE"}
            </span>
          </div>

          {/* Right side: Download button */}
          <button
            onClick={handleDownload}
            disabled={isDownloading}
            className={`
                flex items-center space-x-1 px-2 py-1 text-xs font-medium rounded transition-colors
                ${
                  isDownloading
                    ? "bg-muted text-muted-foreground cursor-not-allowed"
                    : "bg-primary text-primary-foreground hover:bg-primary/90"
                }
              `}
          >
            {isDownloading ? (
              <>
                <div className="animate-spin rounded-full h-3 w-3 border-b-2 border-muted-foreground"></div>
                <span>...</span>
              </>
            ) : (
              <>
                <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                  />
                </svg>
                <span>Download</span>
              </>
            )}
          </button>
        </div>

        {/* Download Error */}
        {downloadError && <p className="mt-1 text-xs text-destructive">{downloadError}</p>}
      </div>

      {/* Image Modal */}
      {showImageModal && isImage && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-75 p-4"
          onClick={() => setShowImageModal(false)}
        >
          <div className="relative max-w-[90vw] max-h-[90vh] flex flex-col">
            {/* Close button */}
            <button
              onClick={() => setShowImageModal(false)}
              className="absolute -top-10 right-0 text-white hover:text-gray-300 z-10"
              title="Close (ESC)"
            >
              <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M6 18L18 6M6 6l12 12"
                />
              </svg>
            </button>

            {/* Image */}
            <Image
              src={`${config.apiUrl}/conversations/files/${attachment.id}/download`}
              alt={attachment.filename}
              width={800}
              height={600}
              className="max-w-full max-h-full object-contain"
              onClick={e => e.stopPropagation()}
              unoptimized
              priority
            />

            {/* Image info */}
            <div className="mt-2 text-center text-white text-sm bg-black bg-opacity-50 px-3 py-2 rounded">
              <p className="font-medium">{attachment.filename}</p>
              <p className="text-xs text-gray-300">
                {formatFileSize(attachment.file_size)} • {formatDate(attachment.created_at)}
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// Compact version for inline display
interface FileAttachmentCompactProps {
  attachment: FileAttachmentType;
  onDownload?: () => void;
  className?: string;
}

export function FileAttachmentCompact({
  attachment,
  onDownload,
  className = "",
}: FileAttachmentCompactProps) {
  const [isDownloading, setIsDownloading] = useState(false);

  const handleDownload = () => {
    if (isDownloading) return;

    setIsDownloading(true);

    try {
      // Create a direct link to the backend endpoint, letting the browser handle the redirect
      const link = document.createElement("a");
      link.href = `${config.apiUrl}/conversations/files/${attachment.id}/download`;
      link.download = attachment.filename;
      link.target = "_blank";
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);

      onDownload?.();
    } catch (error) {
      // eslint-disable-next-line no-console
      console.error("Download error:", error);
    } finally {
      setIsDownloading(false);
    }
  };

  const fileIcon = getFileIcon(attachment.file_type);
  const displayName = getDisplayFileName(attachment.filename, 20);
  const formattedSize = formatFileSize(attachment.file_size);

  return (
    <button
      onClick={handleDownload}
      disabled={isDownloading}
      className={`
        inline-flex items-center space-x-2 px-3 py-2 bg-muted hover:bg-muted/80
        border border-border rounded-lg text-sm transition-colors
        ${isDownloading ? "opacity-50 cursor-not-allowed" : "cursor-pointer"}
        ${className}
      `}
      title={`Download ${attachment.filename}`}
    >
      <span className="text-base">{fileIcon}</span>
      <div className="flex flex-col items-start min-w-0">
        <span className="font-medium text-foreground truncate">{displayName}</span>
        <span className="text-xs text-muted-foreground">{formattedSize}</span>
      </div>
      {isDownloading ? (
        <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-muted-foreground"></div>
      ) : (
        <svg
          className="w-4 h-4 text-muted-foreground"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M12 10v6m0 0l-3-3m3 3l3-3"
          />
        </svg>
      )}
    </button>
  );
}

// List version for multiple attachments
interface FileAttachmentListProps {
  attachments: FileAttachmentType[];
  showPreviews?: boolean;
  maxItems?: number;
  className?: string;
}

export function FileAttachmentList({
  attachments,
  showPreviews = true,
  maxItems = 3,
  className = "",
}: FileAttachmentListProps) {
  const [showAll, setShowAll] = useState(false);

  if (attachments.length === 0) {
    return null;
  }

  const displayedAttachments = showAll ? attachments : attachments.slice(0, maxItems);
  const remainingCount = attachments.length - maxItems;

  return (
    <div className={`space-y-2 ${className}`}>
      <div className="flex flex-wrap gap-2">
        {displayedAttachments.map(attachment => (
          <FileAttachment key={attachment.id} attachment={attachment} showPreview={showPreviews} />
        ))}
      </div>

      {/* Show More Button */}
      {!showAll && remainingCount > 0 && (
        <button
          onClick={() => setShowAll(true)}
          className="text-sm text-primary hover:text-primary/80 font-medium"
        >
          + {remainingCount} more file{remainingCount !== 1 ? "s" : ""}
        </button>
      )}

      {/* Show Less Button */}
      {showAll && attachments.length > maxItems && (
        <button
          onClick={() => setShowAll(false)}
          className="text-sm text-muted-foreground hover:text-foreground font-medium"
        >
          Show less
        </button>
      )}
    </div>
  );
}
