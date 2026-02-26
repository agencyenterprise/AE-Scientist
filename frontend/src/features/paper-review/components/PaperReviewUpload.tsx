"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { FileUp, Loader2, AlertCircle, CheckCircle, Clock } from "lucide-react";
import { cn } from "@/shared/lib/utils";
import { config } from "@/shared/lib/config";
import { withAuthHeaders } from "@/shared/lib/session-token";
import {
  getInsufficientBalanceDetail,
  formatInsufficientBalanceMessage,
} from "@/shared/utils/costs";
import { TierSelector } from "./TierSelector";
import { ConferenceSelector } from "./ConferenceSelector";
import { PaperReviewResult, type AnyPaperReviewDetail } from "./PaperReviewResult";
import type { components } from "@/types/api.gen";

type UploadState = "idle" | "uploading" | "polling" | "complete" | "error";

// Use generated types from OpenAPI schema
type ReviewDetailResponse = AnyPaperReviewDetail;
type PendingReviewSummary = components["schemas"]["PendingReviewSummary"];
type PaperReviewStartedResponse = components["schemas"]["PaperReviewStartedResponse"];

const POLL_INTERVAL_MS = 3000; // Poll every 3 seconds

interface PaperReviewUploadProps {
  onStartNewReview?: () => void;
}

export function PaperReviewUpload({ onStartNewReview }: PaperReviewUploadProps) {
  const [isDragOver, setIsDragOver] = useState(false);
  const [uploadState, setUploadState] = useState<UploadState>("idle");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reviewResult, setReviewResult] = useState<ReviewDetailResponse | null>(null);

  // Track the current review being polled
  const [currentReviewId, setCurrentReviewId] = useState<number | null>(null);
  const [currentReviewFilename, setCurrentReviewFilename] = useState<string | null>(null);
  const [currentReviewStatus, setCurrentReviewStatus] = useState<string | null>(null);
  const [currentProgress, setCurrentProgress] = useState<number | null>(null);
  const [currentProgressStep, setCurrentProgressStep] = useState<string | null>(null);
  const pollTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  // Tier and conference selection
  const [selectedTier, setSelectedTier] = useState<"standard" | "premium">("standard");
  const [selectedConference, setSelectedConference] = useState<"neurips_2025" | "iclr_2025">(
    "neurips_2025"
  );

  // Check for pending reviews on mount
  useEffect(() => {
    async function checkPendingReviews() {
      try {
        const headers = withAuthHeaders(new Headers());
        const response = await fetch(`${config.apiUrl}/paper-reviews/pending`, {
          headers,
          credentials: "include",
        });

        if (response.ok) {
          const data = await response.json();
          if (data.reviews && data.reviews.length > 0) {
            // Resume polling for the most recent pending review
            const pendingReview: PendingReviewSummary = data.reviews[0];
            setCurrentReviewId(pendingReview.id);
            setCurrentReviewFilename(pendingReview.original_filename);
            setCurrentReviewStatus(pendingReview.status);
            setUploadState("polling");
          }
        }
      } catch {
        // Silently ignore errors checking for pending reviews
      }
    }

    checkPendingReviews();

    // Cleanup polling on unmount
    return () => {
      if (pollTimeoutRef.current) {
        clearTimeout(pollTimeoutRef.current);
      }
    };
  }, []);

  // Poll for review completion
  useEffect(() => {
    if (uploadState !== "polling" || !currentReviewId) {
      return;
    }

    async function pollReviewStatus() {
      try {
        const headers = withAuthHeaders(new Headers());
        const response = await fetch(`${config.apiUrl}/paper-reviews/${currentReviewId}`, {
          headers,
          credentials: "include",
        });

        if (!response.ok) {
          throw new Error("Failed to fetch review status");
        }

        const data: ReviewDetailResponse = await response.json();
        setCurrentReviewStatus(data.status);

        // Update progress from response
        setCurrentProgress(data.progress);
        setCurrentProgressStep(data.progress_step);

        if (data.status === "completed") {
          // Check if access is restricted due to insufficient credits
          if (data.access_restricted) {
            // Redirect to the review detail page which will show the locked banner
            window.location.href = `/paper-review/${data.id}`;
            return;
          }

          setReviewResult(data);
          setUploadState("complete");
          setCurrentReviewId(null);
        } else if (data.status === "failed") {
          // Review failed
          setError(data.error_message || "Review failed");
          setUploadState("error");
          setCurrentReviewId(null);
        } else {
          // Still pending or processing - continue polling
          pollTimeoutRef.current = setTimeout(pollReviewStatus, POLL_INTERVAL_MS);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to check review status");
        setUploadState("error");
        setCurrentReviewId(null);
      }
    }

    pollReviewStatus();

    return () => {
      if (pollTimeoutRef.current) {
        clearTimeout(pollTimeoutRef.current);
      }
    };
  }, [uploadState, currentReviewId]);

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
      // Create FormData for file upload
      const formData = new FormData();
      formData.append("file", file);
      formData.append("tier", selectedTier);
      formData.append("conference", selectedConference);

      // Use fetch directly for multipart form data
      const headers = withAuthHeaders(new Headers());
      const response = await fetch(`${config.apiUrl}/paper-reviews`, {
        method: "POST",
        body: formData,
        headers,
        credentials: "include",
      });

      if (!response.ok) {
        const errorData = await response.json();
        // Handle 402 insufficient balance error
        if (response.status === 402) {
          const detail = getInsufficientBalanceDetail(errorData);
          throw new Error(
            formatInsufficientBalanceMessage(detail, "Insufficient balance for review")
          );
        }
        // Handle other errors
        const errorMessage =
          typeof errorData.detail === "string"
            ? errorData.detail
            : errorData.error || "Failed to submit paper for review";
        throw new Error(errorMessage);
      }

      // API returns immediately with review_id and status
      const result: PaperReviewStartedResponse = await response.json();
      setCurrentReviewId(result.review_id);
      setCurrentReviewFilename(file.name);
      setCurrentReviewStatus(result.status);
      setUploadState("polling");
    } catch (err) {
      setError(err instanceof Error ? err.message : "An error occurred");
      setUploadState("error");
    }
  };

  const handleDrop = (e: React.DragEvent) => {
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
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
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
  };

  const handleReset = () => {
    if (pollTimeoutRef.current) {
      clearTimeout(pollTimeoutRef.current);
    }
    setUploadState("idle");
    setSelectedFile(null);
    setError(null);
    setReviewResult(null);
    setCurrentReviewId(null);
    setCurrentReviewFilename(null);
    setCurrentReviewStatus(null);
    setCurrentProgress(null);
    setCurrentProgressStep(null);
    // Notify parent to refresh the history list
    onStartNewReview?.();
  };

  // Show result if review is complete
  if (uploadState === "complete" && reviewResult) {
    return (
      <div className="space-y-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex flex-wrap items-center gap-2">
            <CheckCircle className="h-5 w-5 shrink-0 text-emerald-400" />
            <span className="font-medium text-emerald-400">Review Complete</span>
            {(selectedFile || currentReviewFilename) && (
              <span className="truncate text-slate-400">
                for {selectedFile?.name || currentReviewFilename}
              </span>
            )}
            <span className="rounded bg-slate-700/50 px-1.5 py-0.5 text-[10px] font-medium text-slate-300">
              {reviewResult.conference === "neurips_2025"
                ? "NeurIPS 2025"
                : reviewResult.conference === "iclr_2025"
                  ? "ICLR 2025"
                  : "ICML"}
            </span>
            <span
              className={cn(
                "rounded px-1.5 py-0.5 text-[10px] font-medium",
                reviewResult.tier === "premium"
                  ? "bg-sky-500/10 text-sky-400"
                  : "bg-amber-500/10 text-amber-400"
              )}
            >
              {reviewResult.tier === "premium" ? "Premium" : "Standard"}
            </span>
          </div>
          <button
            onClick={handleReset}
            className="w-full rounded-lg border border-slate-700 px-4 py-2 text-sm text-slate-300 transition-colors hover:bg-slate-800 sm:w-auto"
          >
            Upload Another Paper
          </button>
        </div>
        <PaperReviewResult data={reviewResult} />
      </div>
    );
  }

  // Show loading/polling state
  if (uploadState === "uploading" || uploadState === "polling") {
    // Use progress step if available, otherwise fall back to status-based text
    const statusText =
      currentProgressStep ||
      (currentReviewStatus === "processing"
        ? "Analyzing paper with AI..."
        : currentReviewStatus === "pending"
          ? "Starting analysis..."
          : "Uploading paper...");

    const progressPercent = currentProgress !== null ? Math.round(currentProgress * 100) : null;

    return (
      <div className="flex flex-col items-center justify-center rounded-xl border-2 border-dashed border-slate-700 bg-slate-900/50 p-6 sm:p-12">
        <Loader2 className="mb-3 h-10 w-10 animate-spin text-amber-400 sm:mb-4 sm:h-12 sm:w-12" />
        <p className="text-center text-base font-medium text-white sm:text-lg">{statusText}</p>
        <p className="mt-2 truncate text-sm text-slate-400">
          {selectedFile?.name || currentReviewFilename}
        </p>
        <div className="mt-2 flex items-center gap-2">
          <span className="rounded bg-slate-700/50 px-1.5 py-0.5 text-[10px] font-medium text-slate-300">
            {selectedConference === "neurips_2025"
              ? "NeurIPS 2025"
              : selectedConference === "iclr_2025"
                ? "ICLR 2025"
                : "ICML"}
          </span>
          <span
            className={cn(
              "rounded px-1.5 py-0.5 text-[10px] font-medium",
              selectedTier === "premium"
                ? "bg-sky-500/10 text-sky-400"
                : "bg-amber-500/10 text-amber-400"
            )}
          >
            {selectedTier === "premium" ? "Premium" : "Standard"}
          </span>
        </div>

        {/* Progress bar */}
        {progressPercent !== null && (
          <div className="mt-4 w-full max-w-xs">
            <div className="h-2 overflow-hidden rounded-full bg-slate-700">
              <div
                className="h-full rounded-full bg-amber-400 transition-all duration-500 ease-out"
                style={{ width: `${progressPercent}%` }}
              />
            </div>
            <p className="mt-2 text-center text-sm text-slate-400">{progressPercent}% complete</p>
          </div>
        )}

        <div className="mt-4 flex items-center gap-2 text-center text-xs text-slate-500">
          <Clock className="h-3 w-3 shrink-0" />
          <span>This process runs in the background - you can refresh the page safely</span>
        </div>
        <button
          onClick={handleReset}
          className="mt-4 w-full rounded-lg border border-slate-600 px-4 py-2 text-sm text-slate-300 transition-colors hover:bg-slate-800 sm:w-auto"
        >
          Start New Review
        </button>
      </div>
    );
  }

  // Show error state
  if (uploadState === "error") {
    return (
      <div className="flex flex-col items-center justify-center rounded-xl border-2 border-dashed border-red-500/50 bg-red-500/5 p-6 sm:p-12">
        <AlertCircle className="mb-3 h-10 w-10 text-red-400 sm:mb-4 sm:h-12 sm:w-12" />
        <p className="text-base font-medium text-white sm:text-lg">Review Failed</p>
        <p className="mt-2 text-center text-sm text-red-400">{error}</p>
        <button
          onClick={handleReset}
          className="mt-4 w-full rounded-lg bg-slate-800 px-4 py-2 text-sm text-white transition-colors hover:bg-slate-700 sm:w-auto"
        >
          Try Again
        </button>
      </div>
    );
  }

  // Default upload state
  return (
    <div className="space-y-4">
      {/* Tier selector */}
      <TierSelector selectedTier={selectedTier} onTierChange={setSelectedTier} />

      {/* Conference selector */}
      <div className="flex items-center gap-3">
        <span className="text-sm text-slate-400">Conference:</span>
        <ConferenceSelector
          selectedConference={selectedConference}
          onConferenceChange={setSelectedConference}
        />
      </div>

      {error && (
        <div className="flex items-center gap-2 rounded-lg bg-red-500/10 p-3 text-sm text-red-400">
          <AlertCircle className="h-4 w-4 shrink-0" />
          {error}
        </div>
      )}

      <label
        className={`flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed p-6 transition-colors sm:p-12 ${
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
        <FileUp
          className={`mb-3 h-10 w-10 sm:mb-4 sm:h-12 sm:w-12 ${isDragOver ? "text-amber-400" : "text-slate-500"}`}
        />
        <p className="text-center text-base font-medium text-white sm:text-lg">
          {isDragOver ? "Drop your PDF here" : "Upload a research paper"}
        </p>
        <p className="mt-2 text-center text-sm text-slate-400">
          Drag and drop a PDF file, or click to browse
        </p>
        <p className="mt-1 text-xs text-slate-500">Maximum file size: 50MB</p>
      </label>
    </div>
  );
}
