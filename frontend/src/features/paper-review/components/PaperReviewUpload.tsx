"use client";

import { useCallback, useState } from "react";
import { FileUp, Loader2, AlertCircle, CheckCircle } from "lucide-react";
import { PaperReviewResult, type PaperReviewResponse } from "./PaperReviewResult";

type UploadState = "idle" | "uploading" | "reviewing" | "complete" | "error";

export function PaperReviewUpload() {
  const [isDragOver, setIsDragOver] = useState(false);
  const [uploadState, setUploadState] = useState<UploadState>("idle");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reviewResult, setReviewResult] = useState<PaperReviewResponse | null>(null);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
  }, []);

  const validateFile = (file: File): string | null => {
    if (file.type !== "application/pdf") {
      return "Please upload a PDF file";
    }
    if (file.size > 50 * 1024 * 1024) {
      // 50MB limit
      return "File size must be less than 50MB";
    }
    return null;
  };

  const submitForReview = async (file: File) => {
    setUploadState("uploading");
    setError(null);
    setReviewResult(null);

    try {
      setUploadState("reviewing");

      // Create FormData for file upload
      const formData = new FormData();
      formData.append("file", file);

      // Use fetch directly for multipart form data
      const response = await fetch("/api/paper-reviews", {
        method: "POST",
        body: formData,
        credentials: "include",
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || errorData.detail || "Failed to submit paper for review");
      }

      const result: PaperReviewResponse = await response.json();
      setReviewResult(result);
      setUploadState("complete");
    } catch (err) {
      setError(err instanceof Error ? err.message : "An error occurred");
      setUploadState("error");
    }
  };

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);

    const files = e.dataTransfer.files;
    const file = files[0];
    if (file) {
      const validationError = validateFile(file);
      if (validationError) {
        setError(validationError);
        return;
      }
      setSelectedFile(file);
      submitForReview(file);
    }
  }, []);

  const handleFileSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    const file = files?.[0];
    if (file) {
      const validationError = validateFile(file);
      if (validationError) {
        setError(validationError);
        return;
      }
      setSelectedFile(file);
      submitForReview(file);
    }
  }, []);

  const handleReset = () => {
    setUploadState("idle");
    setSelectedFile(null);
    setError(null);
    setReviewResult(null);
  };

  // Show result if review is complete
  if (uploadState === "complete" && reviewResult) {
    return (
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-emerald-400">
            <CheckCircle className="h-5 w-5" />
            <span className="font-medium">Review Complete</span>
            {selectedFile && <span className="text-slate-400">for {selectedFile.name}</span>}
          </div>
          <button
            onClick={handleReset}
            className="rounded-lg border border-slate-700 px-4 py-2 text-sm text-slate-300 transition-colors hover:bg-slate-800"
          >
            Upload Another Paper
          </button>
        </div>
        <PaperReviewResult review={reviewResult} />
      </div>
    );
  }

  // Show loading state
  if (uploadState === "uploading" || uploadState === "reviewing") {
    return (
      <div className="flex flex-col items-center justify-center rounded-xl border-2 border-dashed border-slate-700 bg-slate-900/50 p-12">
        <Loader2 className="mb-4 h-12 w-12 animate-spin text-amber-400" />
        <p className="text-lg font-medium text-white">
          {uploadState === "uploading" ? "Uploading paper..." : "Analyzing paper..."}
        </p>
        <p className="mt-2 text-sm text-slate-400">{selectedFile?.name}</p>
        <p className="mt-4 text-xs text-slate-500">
          This may take a few minutes depending on the paper length
        </p>
      </div>
    );
  }

  // Show error state
  if (uploadState === "error") {
    return (
      <div className="flex flex-col items-center justify-center rounded-xl border-2 border-dashed border-red-500/50 bg-red-500/5 p-12">
        <AlertCircle className="mb-4 h-12 w-12 text-red-400" />
        <p className="text-lg font-medium text-white">Review Failed</p>
        <p className="mt-2 text-sm text-red-400">{error}</p>
        <button
          onClick={handleReset}
          className="mt-4 rounded-lg bg-slate-800 px-4 py-2 text-sm text-white transition-colors hover:bg-slate-700"
        >
          Try Again
        </button>
      </div>
    );
  }

  // Default upload state
  return (
    <div>
      {error && (
        <div className="mb-4 flex items-center gap-2 rounded-lg bg-red-500/10 p-3 text-sm text-red-400">
          <AlertCircle className="h-4 w-4" />
          {error}
        </div>
      )}

      <label
        className={`flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed p-12 transition-colors ${
          isDragOver
            ? "border-amber-500 bg-amber-500/10"
            : "border-slate-700 bg-slate-900/50 hover:border-slate-600 hover:bg-slate-900"
        }`}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        <input
          type="file"
          accept="application/pdf"
          onChange={handleFileSelect}
          className="hidden"
        />
        <FileUp className={`mb-4 h-12 w-12 ${isDragOver ? "text-amber-400" : "text-slate-500"}`} />
        <p className="text-lg font-medium text-white">
          {isDragOver ? "Drop your PDF here" : "Upload a research paper"}
        </p>
        <p className="mt-2 text-sm text-slate-400">Drag and drop a PDF file, or click to browse</p>
        <p className="mt-1 text-xs text-slate-500">Maximum file size: 50MB</p>
      </label>
    </div>
  );
}
