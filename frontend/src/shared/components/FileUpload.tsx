"use client";

import { useCallback, useState } from "react";
import Image from "next/image";

import { config } from "@/shared/lib/config";
import {
  createImagePreview,
  formatFileSize,
  generateUploadId,
  getDisplayFileName,
  getFileIcon,
  getFilesFromDragEvent,
  hasFiles,
  isImageFile,
  validateFile,
} from "@/shared/lib/fileUtils";
import type { FileMetadata } from "@/types";
import { isErrorResponse } from "@/shared/lib/api-adapters";

interface UploadProgress {
  uploadId: string;
  file: File;
  progress: number;
  status: "pending" | "uploading" | "completed" | "error";
  error?: string;
  uploadedFile?: FileMetadata;
  previewUrl?: string;
}

interface ModelCapabilities {
  supportsImages: boolean;
  supportsPdfs: boolean;
}

interface FileUploadProps {
  conversationId: number;
  onFilesUploaded: (files: FileMetadata[]) => void;
  onUploadProgress?: (progress: UploadProgress[]) => void;
  disabled?: boolean;
  maxFiles?: number;
  currentModel: string;
  currentProvider: string;
  modelCapabilities: ModelCapabilities;
}

export function FileUpload({
  conversationId,
  onFilesUploaded,
  onUploadProgress,
  disabled = false,
  maxFiles = 5,
  currentModel,
  currentProvider,
  modelCapabilities,
}: FileUploadProps) {
  const [isDragOver, setIsDragOver] = useState(false);
  const [uploads, setUploads] = useState<UploadProgress[]>([]);

  // Check if file type is supported by current model
  const isFileTypeSupported = useCallback(
    (file: File) => {
      const { supportsImages, supportsPdfs } = modelCapabilities;
      const fileType = file.type;

      if (fileType.startsWith("image/")) {
        return supportsImages;
      }

      if (fileType === "application/pdf") {
        return supportsPdfs;
      }

      // Text files are always supported
      if (fileType === "text/plain") {
        return true;
      }

      return false; // Unsupported file type
    },
    [modelCapabilities]
  );

  const getUnsupportedFileTypes = () => {
    const unsupported = [];
    if (!modelCapabilities.supportsImages) {
      unsupported.push("images");
    }
    if (!modelCapabilities.supportsPdfs) {
      unsupported.push("PDFs");
    }
    return unsupported;
  };

  const updateUpload = useCallback(
    (uploadId: string, updates: Partial<UploadProgress>) => {
      setUploads(prev => {
        const newUploads = prev.map(upload =>
          upload.uploadId === uploadId ? { ...upload, ...updates } : upload
        );
        if (onUploadProgress) {
          onUploadProgress(newUploads);
        }
        return newUploads;
      });
    },
    [onUploadProgress]
  );

  const uploadFile = useCallback(
    async (uploadProgress: UploadProgress) => {
      const { uploadId, file } = uploadProgress;

      try {
        updateUpload(uploadId, { status: "uploading", progress: 0 });

        const formData = new FormData();
        formData.append("file", file);
        formData.append("llm_model", currentModel);
        formData.append("llm_provider", currentProvider);

        const response = await fetch(`${config.apiUrl}/conversations/${conversationId}/files`, {
          method: "POST",
          credentials: "include", // Include authentication cookies
          body: formData,
        });

        if (!response.ok) {
          const errorData = await response.json().catch(() => ({ error: "Upload failed" }));
          throw new Error(errorData.error || `HTTP ${response.status}`);
        }

        const result: import("@/types").ApiComponents["schemas"]["FileUploadResponse"] =
          await response.json();

        if (isErrorResponse(result)) {
          throw new Error(result.error || "Upload failed");
        }

        updateUpload(uploadId, {
          status: "completed",
          progress: 100,
          uploadedFile: result.file,
        });

        return result.file;
      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : "Upload failed";
        updateUpload(uploadId, {
          status: "error",
          error: errorMessage,
        });
        throw error;
      }
    },
    [conversationId, currentModel, currentProvider, updateUpload]
  );

  const processFiles = useCallback(
    async (files: File[]) => {
      if (disabled) return;

      // Validate file count
      const currentCount = uploads.filter(u => u.status === "completed").length;
      const totalCount = currentCount + files.length;

      if (totalCount > maxFiles) {
        alert(
          `Maximum ${maxFiles} files allowed. You can upload ${maxFiles - currentCount} more files.`
        );
        return;
      }

      // Validate and create upload progress objects
      const newUploads: UploadProgress[] = [];
      const validFiles: File[] = [];

      for (const file of files) {
        const validation = validateFile(file);
        const uploadId = generateUploadId();

        if (!validation.isValid) {
          newUploads.push({
            uploadId,
            file,
            progress: 0,
            status: "error",
            error: validation.errors.join(", "),
          });
          continue;
        }

        // Check model compatibility for this file type
        if (!isFileTypeSupported(file)) {
          const fileTypeLabel = file.type.startsWith("image/")
            ? "image"
            : file.type === "application/pdf"
              ? "PDF"
              : file.type;

          newUploads.push({
            uploadId,
            file,
            progress: 0,
            status: "error",
            error: `${fileTypeLabel} files are not supported by ${currentModel}. Switch to a compatible model to upload this file.`,
          });
          continue;
        }

        // Create preview URL for images
        let previewUrl: string | undefined;
        if (isImageFile(file.type)) {
          try {
            previewUrl = createImagePreview(file);
          } catch (err) {
            // eslint-disable-next-line no-console
            console.warn("Failed to create image preview:", err);
          }
        }

        newUploads.push({
          uploadId,
          file,
          progress: 0,
          status: "pending",
          previewUrl,
        });
        validFiles.push(file);
      }

      // Add all uploads to state
      setUploads(prev => [...prev, ...newUploads]);

      // Upload valid files
      const uploadPromises = newUploads
        .filter(upload => upload.status === "pending")
        .map(upload => uploadFile(upload));

      try {
        const uploadedFiles = await Promise.allSettled(uploadPromises);
        const successfulUploads = uploadedFiles
          .filter(
            (result): result is PromiseFulfilledResult<FileMetadata> =>
              result.status === "fulfilled"
          )
          .map(result => result.value);

        if (successfulUploads.length > 0) {
          onFilesUploaded(successfulUploads);
        }
      } catch (error) {
        // eslint-disable-next-line no-console
        console.error("Upload error:", error);
      }
    },
    [disabled, uploads, maxFiles, uploadFile, onFilesUploaded, currentModel, isFileTypeSupported]
  );

  const handleDragOver = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      if (!disabled && hasFiles(e.nativeEvent)) {
        setIsDragOver(true);
      }
    },
    [disabled]
  );

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      setIsDragOver(false);

      if (disabled) return;

      const files = getFilesFromDragEvent(e.nativeEvent);
      if (files.length > 0) {
        processFiles(files);
      }
    },
    [disabled, processFiles]
  );

  const handleFileSelect = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const files = Array.from(e.target.files || []);
      if (files.length > 0) {
        processFiles(files);
      }
      // Reset input value to allow selecting the same file again
      e.target.value = "";
    },
    [processFiles]
  );

  const removeUpload = useCallback((uploadId: string) => {
    setUploads(prev => {
      const upload = prev.find(u => u.uploadId === uploadId);
      if (upload?.previewUrl) {
        URL.revokeObjectURL(upload.previewUrl);
      }
      return prev.filter(u => u.uploadId !== uploadId);
    });
  }, []);

  const clearAllUploads = useCallback(() => {
    // Cleanup preview URLs
    uploads.forEach(upload => {
      if (upload.previewUrl) {
        URL.revokeObjectURL(upload.previewUrl);
      }
    });
    setUploads([]);
  }, [uploads]);

  const getCompletedFiles = useCallback((): FileMetadata[] => {
    return uploads
      .filter(upload => upload.status === "completed" && upload.uploadedFile)
      .map(upload => upload.uploadedFile as FileMetadata)
      .filter(Boolean);
  }, [uploads]);

  // Expose completed files for parent component
  const completedFiles = getCompletedFiles();

  return (
    <div className="w-full">
      {/* Upload Area */}
      <div
        className={`
          border-2 border-dashed rounded-lg p-6 text-center transition-colors
          ${isDragOver ? "border-primary bg-primary/10" : "border-border hover:border-primary/50"}
          ${disabled ? "opacity-50 cursor-not-allowed" : "cursor-pointer"}
        `}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => {
          if (!disabled) {
            document.getElementById("file-input")?.click();
          }
        }}
      >
        <div className="flex flex-col items-center space-y-2">
          <div className="text-4xl">📁</div>
          <div>
            <p className="text-sm font-medium text-foreground">
              {isDragOver ? "Drop files here" : "Click to upload or drag and drop"}
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              {(() => {
                const supportedTypes = [];
                if (modelCapabilities.supportsImages) {
                  supportedTypes.push("Images (JPEG, PNG, GIF, WebP, SVG)");
                }
                if (modelCapabilities.supportsPdfs) {
                  supportedTypes.push("PDF documents");
                }
                supportedTypes.push("Text files");

                return `${supportedTypes.join(", ")} up to 10MB`;
              })()}
            </p>
            {getUnsupportedFileTypes().length > 0 && (
              <p className="text-xs text-orange-600 mt-1">
                ⚠️ Current model ({currentModel}) doesn&apos;t support{" "}
                {getUnsupportedFileTypes().join(" or ")}
              </p>
            )}
            <p className="text-xs text-muted-foreground/60 mt-1">
              Maximum {maxFiles} files • {completedFiles.length} uploaded
            </p>
          </div>
        </div>

        <input
          id="file-input"
          type="file"
          multiple
          accept=".jpg,.jpeg,.png,.gif,.webp,.svg,.pdf,.txt"
          onChange={handleFileSelect}
          disabled={disabled}
          className="hidden"
        />
      </div>

      {/* Upload Progress List */}
      {uploads.length > 0 && (
        <div className="mt-4 space-y-2 max-h-60 overflow-y-auto">
          <div className="flex items-center justify-between">
            <h4 className="text-sm font-medium text-foreground">Files ({uploads.length})</h4>
            <button
              onClick={clearAllUploads}
              className="text-xs text-muted-foreground hover:text-foreground"
            >
              Clear all
            </button>
          </div>

          {uploads.map(upload => (
            <div key={upload.uploadId} className="border border-border rounded-lg p-3 bg-card">
              <div className="flex items-start space-x-3">
                {/* File Icon/Preview */}
                <div className="flex-shrink-0 w-10 h-10 flex items-center justify-center">
                  {upload.previewUrl ? (
                    <Image
                      src={upload.previewUrl}
                      alt={upload.file.name}
                      width={40}
                      height={40}
                      className="w-10 h-10 object-cover rounded"
                      unoptimized
                    />
                  ) : (
                    <span className="text-lg">{getFileIcon(upload.file.type)}</span>
                  )}
                </div>

                {/* File Info */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between">
                    <p className="text-sm font-medium text-foreground truncate">
                      {getDisplayFileName(upload.file.name)}
                    </p>
                    <button
                      onClick={() => removeUpload(upload.uploadId)}
                      className="text-muted-foreground hover:text-foreground ml-2"
                      title="Remove file"
                    >
                      ✕
                    </button>
                  </div>

                  <p className="text-xs text-muted-foreground">
                    {formatFileSize(upload.file.size)} • {upload.file.type}
                  </p>

                  {/* Status */}
                  <div className="mt-2">
                    {upload.status === "pending" && (
                      <div className="text-xs text-muted-foreground">Waiting...</div>
                    )}

                    {upload.status === "uploading" && (
                      <div className="space-y-1">
                        <div className="text-xs text-primary">Uploading...</div>
                        <div className="w-full bg-muted rounded-full h-1">
                          <div
                            className="bg-primary h-1 rounded-full transition-all"
                            style={{ width: `${upload.progress}%` }}
                          />
                        </div>
                      </div>
                    )}

                    {upload.status === "completed" && (
                      <div className="text-xs text-green-400 flex items-center">
                        <span className="mr-1">✓</span>
                        Uploaded successfully
                      </div>
                    )}

                    {upload.status === "error" && (
                      <div className="text-xs text-destructive">⚠️ {upload.error}</div>
                    )}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
