"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { FileUp, Loader2, AlertCircle, CheckCircle, Clock } from "lucide-react";
import { config } from "@/shared/lib/config";
import { withAuthHeaders } from "@/shared/lib/session-token";
import { ModelSelector } from "@/features/model-selector/components/ModelSelector";
import { PromptTypes } from "@/shared/lib/prompt-types";
import { PaperReviewResult, type PaperReviewResponse } from "./PaperReviewResult";

type UploadState = "idle" | "uploading" | "polling" | "complete" | "error";

interface PendingReview {
  id: number;
  status: string;
  original_filename: string;
  model: string;
  created_at: string;
}

interface ReviewDetailResponse {
  id: number;
  status: string;
  error_message?: string | null;
  summary?: string | null;
  strengths?: string[] | null;
  weaknesses?: string[] | null;
  originality?: number | null;
  quality?: number | null;
  clarity?: number | null;
  significance?: number | null;
  questions?: string[] | null;
  limitations?: string[] | null;
  ethical_concerns?: boolean | null;
  soundness?: number | null;
  presentation?: number | null;
  contribution?: number | null;
  overall?: number | null;
  confidence?: number | null;
  decision?: string | null;
  original_filename: string;
  model: string;
  created_at: string;
  token_usage?: {
    input_tokens: number;
    cached_input_tokens: number;
    output_tokens: number;
  } | null;
  credits_charged?: number;
}

const POLL_INTERVAL_MS = 3000; // Poll every 3 seconds

export function PaperReviewUpload() {
  const [isDragOver, setIsDragOver] = useState(false);
  const [uploadState, setUploadState] = useState<UploadState>("idle");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reviewResult, setReviewResult] = useState<PaperReviewResponse | null>(null);

  // Track the current review being polled
  const [currentReviewId, setCurrentReviewId] = useState<number | null>(null);
  const [currentReviewFilename, setCurrentReviewFilename] = useState<string | null>(null);
  const [currentReviewStatus, setCurrentReviewStatus] = useState<string | null>(null);
  const pollTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  // Model selection state
  const [selectedModel, setSelectedModel] = useState<string>("");
  const [selectedProvider, setSelectedProvider] = useState<string>("");
  const [currentModel, setCurrentModel] = useState<string>("");
  const [currentProvider, setCurrentProvider] = useState<string>("");

  const handleModelChange = useCallback((model: string, provider: string) => {
    setSelectedModel(model);
    setSelectedProvider(provider);
  }, []);

  const handleDefaultsChange = useCallback((model: string, provider: string) => {
    setCurrentModel(model);
    setCurrentProvider(provider);
  }, []);

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
            const pendingReview: PendingReview = data.reviews[0];
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

        if (data.status === "completed") {
          // Review is complete - transform to the format PaperReviewResult expects
          const result: PaperReviewResponse = {
            id: data.id,
            review: {
              summary: data.summary || "",
              strengths: data.strengths || [],
              weaknesses: data.weaknesses || [],
              questions: data.questions || [],
              limitations: data.limitations || [],
              ethical_concerns: data.ethical_concerns || false,
              originality: data.originality || 0,
              quality: data.quality || 0,
              clarity: data.clarity || 0,
              significance: data.significance || 0,
              soundness: data.soundness || 0,
              presentation: data.presentation || 0,
              contribution: data.contribution || 0,
              overall: data.overall || 0,
              confidence: data.confidence || 0,
              decision: data.decision || "",
            },
            token_usage: data.token_usage || {
              input_tokens: 0,
              cached_input_tokens: 0,
              output_tokens: 0,
            },
            credits_charged: data.credits_charged || 0,
            original_filename: data.original_filename,
            model: data.model,
            created_at: data.created_at,
          };
          setReviewResult(result);
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

      // Use the selected model or fall back to current default
      const effectiveModel = selectedModel || currentModel;
      const effectiveProvider = selectedProvider || currentProvider;
      if (effectiveModel && effectiveProvider) {
        // Format as "provider/model" for the API
        formData.append("model", `${effectiveProvider}/${effectiveModel}`);
      }

      // Review parameters (hardcoded for now, user can't configure these yet)
      formData.append("num_reviews_ensemble", "3");
      formData.append("num_reflections", "2");

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
        throw new Error(errorData.error || errorData.detail || "Failed to submit paper for review");
      }

      // API returns immediately with review_id and status
      const result = await response.json();
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
  };

  // Show result if review is complete
  if (uploadState === "complete" && reviewResult) {
    return (
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-emerald-400">
            <CheckCircle className="h-5 w-5" />
            <span className="font-medium">Review Complete</span>
            {(selectedFile || currentReviewFilename) && (
              <span className="text-slate-400">for {selectedFile?.name || currentReviewFilename}</span>
            )}
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

  // Show loading/polling state
  if (uploadState === "uploading" || uploadState === "polling") {
    const statusText =
      currentReviewStatus === "processing"
        ? "Analyzing paper with AI..."
        : currentReviewStatus === "pending"
          ? "Starting analysis..."
          : "Uploading paper...";

    return (
      <div className="flex flex-col items-center justify-center rounded-xl border-2 border-dashed border-slate-700 bg-slate-900/50 p-12">
        <Loader2 className="mb-4 h-12 w-12 animate-spin text-amber-400" />
        <p className="text-lg font-medium text-white">{statusText}</p>
        <p className="mt-2 text-sm text-slate-400">
          {selectedFile?.name || currentReviewFilename}
        </p>
        <div className="mt-4 flex items-center gap-2 text-xs text-slate-500">
          <Clock className="h-3 w-3" />
          <span>This process runs in the background - you can refresh the page safely</span>
        </div>
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
      {/* Model selector */}
      <div className="mb-4 flex items-center justify-between">
        <span className="text-sm text-slate-400">Select AI model for review:</span>
        <ModelSelector
          promptType={PromptTypes.PAPER_REVIEW}
          onModelChange={handleModelChange}
          onDefaultsChange={handleDefaultsChange}
          selectedModel={selectedModel}
          selectedProvider={selectedProvider}
          showMakeDefault={true}
          showCapabilities={false}
        />
      </div>

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
