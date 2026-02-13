"use client";

import {
  AlertCircle,
  FileText,
  Loader2,
  Settings2,
  Upload,
} from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import { Button } from "@/shared/components/ui/button";
import { Progress } from "@/shared/components/ui/progress";

import { fetchPaperReview, submitPaperReview } from "../api";
import { ModelSelector } from "./ModelSelector";
import { PaperReviewResult } from "./PaperReviewResult";

const MODEL_COOKIE_NAME = "ae-paper-review-model";
const COOKIE_MAX_AGE_DAYS = 365;

function getModelFromCookie(): string {
  if (typeof document === "undefined") return "";
  const match = document.cookie.match(
    new RegExp(`(^| )${MODEL_COOKIE_NAME}=([^;]+)`),
  );
  return match ? decodeURIComponent(match[2]) : "";
}

function saveModelToCookie(modelId: string): void {
  if (typeof document === "undefined") return;
  const maxAge = COOKIE_MAX_AGE_DAYS * 24 * 60 * 60;
  document.cookie = `${MODEL_COOKIE_NAME}=${encodeURIComponent(modelId)}; path=/; max-age=${maxAge}; SameSite=Lax`;
}

interface PaperReviewUploadProps {
  onReviewStarted?: () => void;
}

export function PaperReviewUpload({ onReviewStarted }: PaperReviewUploadProps) {
  const [file, setFile] = useState<File | null>(null);
  const [model, setModel] = useState(() => getModelFromCookie());
  const [numReviews, setNumReviews] = useState(3);
  const [numReflections, setNumReflections] = useState(1);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeReviewId, setActiveReviewId] = useState<number | null>(null);
  const [reviewData, setReviewData] = useState<Awaited<
    ReturnType<typeof fetchPaperReview>
  > | null>(null);
  const pollingRef = useRef<NodeJS.Timeout | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Handle model change and persist to cookie
  const handleModelChange = useCallback((newModel: string) => {
    setModel(newModel);
    if (newModel) {
      saveModelToCookie(newModel);
    }
  }, []);

  // Clean up polling on unmount
  useEffect(() => {
    return () => {
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
      }
    };
  }, []);

  // Poll for review completion
  useEffect(() => {
    if (!activeReviewId) return;

    const pollReview = async () => {
      try {
        const data = await fetchPaperReview(activeReviewId);
        setReviewData(data);

        if (data.status === "completed" || data.status === "failed") {
          if (pollingRef.current) {
            clearInterval(pollingRef.current);
            pollingRef.current = null;
          }
        }
      } catch {
        // Ignore polling errors
      }
    };

    // Initial fetch
    pollReview();

    // Start polling
    pollingRef.current = setInterval(pollReview, 3000);

    return () => {
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
        pollingRef.current = null;
      }
    };
  }, [activeReviewId]);

  const handleFileChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const selectedFile = e.target.files?.[0];
      if (selectedFile) {
        if (!selectedFile.name.toLowerCase().endsWith(".pdf")) {
          setError("Please select a PDF file");
          return;
        }
        if (selectedFile.size > 50 * 1024 * 1024) {
          setError("File size must be less than 50MB");
          return;
        }
        setFile(selectedFile);
        setError(null);
      }
    },
    [],
  );

  const handleDrop = useCallback((e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    const droppedFile = e.dataTransfer.files[0];
    if (droppedFile) {
      if (!droppedFile.name.toLowerCase().endsWith(".pdf")) {
        setError("Please select a PDF file");
        return;
      }
      if (droppedFile.size > 50 * 1024 * 1024) {
        setError("File size must be less than 50MB");
        return;
      }
      setFile(droppedFile);
      setError(null);
    }
  }, []);

  const handleSubmit = async () => {
    if (!file || !model) {
      setError("Please select a file and model");
      return;
    }

    setIsUploading(true);
    setError(null);
    // Scroll to top so user sees the uploading state
    setTimeout(() => {
      window.scrollTo({ top: 0, behavior: "smooth" });
    }, 0);

    try {
      const result = await submitPaperReview({
        file,
        model,
        numReviewsEnsemble: numReviews,
        numReflections,
      });

      setActiveReviewId(result.review_id);
      setFile(null);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
      onReviewStarted?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to submit review");
    } finally {
      setIsUploading(false);
    }
  };

  const handleStartNew = () => {
    setActiveReviewId(null);
    setReviewData(null);
    setFile(null);
    setError(null);
    // Scroll to top after state update and re-render
    setTimeout(() => {
      window.scrollTo({ top: 0, behavior: "smooth" });
    }, 0);
  };

  // Show uploading state immediately when upload starts
  if (isUploading) {
    return (
      <div className="space-y-4 sm:space-y-6">
        <div className="text-center px-2">
          <Loader2 className="mx-auto mb-3 h-10 w-10 animate-spin text-sky-500 sm:mb-4 sm:h-12 sm:w-12" />
          <h3 className="mb-2 text-base font-medium text-white sm:text-lg">
            Uploading your paper...
          </h3>
          <p className="text-sm text-slate-400 sm:text-base">
            {file?.name || "Preparing upload..."}
          </p>
          <p className="mt-4 text-xs text-slate-500">
            This may take a moment for larger files
          </p>
        </div>
      </div>
    );
  }

  // Show result if we have a completed or failed review
  if (
    reviewData &&
    (reviewData.status === "completed" || reviewData.status === "failed")
  ) {
    return (
      <div className="space-y-4">
        <PaperReviewResult review={reviewData} />
        <Button onClick={handleStartNew} variant="outline" className="w-full">
          Start New Review
        </Button>
      </div>
    );
  }

  // Show progress if we have an active review (even if reviewData hasn't loaded yet)
  if (activeReviewId) {
    return (
      <div className="space-y-4 sm:space-y-6">
        <div className="text-center px-2">
          <Loader2 className="mx-auto mb-3 h-10 w-10 animate-spin text-sky-500 sm:mb-4 sm:h-12 sm:w-12" />
          <h3 className="mb-2 text-base font-medium text-white sm:text-lg">
            Reviewing your paper...
          </h3>
          <p className="mb-4 text-sm text-slate-400 sm:text-base">
            {reviewData?.progress_step || "Starting review..."}
          </p>
          <Progress
            value={(reviewData?.progress ?? 0) * 100}
            className="mx-auto max-w-md"
          />
          <p className="mt-2 text-xs text-slate-500 sm:text-sm">
            {Math.round((reviewData?.progress ?? 0) * 100)}% complete
          </p>
          <p className="mt-4 text-xs text-slate-600">
            This runs in the background — you can start another review
          </p>
          <Button onClick={handleStartNew} variant="outline" className="mt-4">
            Start New Review
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 sm:space-y-8">
      {/* File Upload Area */}
      <div
        onDrop={handleDrop}
        onDragOver={(e) => e.preventDefault()}
        onClick={() => fileInputRef.current?.click()}
        className={`border-2 border-dashed rounded-xl p-5 sm:p-8 text-center cursor-pointer transition-all duration-200 ${
          file
            ? "border-sky-500 bg-sky-500/10"
            : "border-slate-700 hover:border-slate-500 bg-slate-900/30 hover:bg-slate-900/50"
        }`}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf"
          onChange={handleFileChange}
          className="hidden"
        />
        {file ? (
          <div className="flex items-center justify-center gap-3 max-w-full">
            <div className="p-2 rounded-lg bg-sky-500/20 shrink-0">
              <FileText className="h-5 w-5 sm:h-6 sm:w-6 text-sky-400" />
            </div>
            <div className="text-left min-w-0">
              <p className="font-medium text-white text-sm sm:text-base truncate">
                {file.name}
              </p>
              <p className="text-xs sm:text-sm text-slate-400">
                {(file.size / 1024 / 1024).toFixed(2)} MB
              </p>
            </div>
          </div>
        ) : (
          <>
            <div className="p-2 sm:p-3 rounded-xl bg-slate-800/50 w-fit mx-auto mb-3 sm:mb-4">
              <Upload className="h-6 w-6 sm:h-8 sm:w-8 text-slate-400" />
            </div>
            <p className="text-slate-200 font-medium mb-1 text-sm sm:text-base">
              Drop your PDF here or click to browse
            </p>
            <p className="text-xs sm:text-sm text-slate-500">
              Maximum file size: 50MB
            </p>
          </>
        )}
      </div>

      {/* Model Selection */}
      <div className="space-y-3">
        <h3 className="text-base font-semibold text-white">Select Model</h3>
        <ModelSelector value={model} onChange={handleModelChange} />
      </div>

      {/* Review Settings */}
      <div className="space-y-3">
        <div className="flex items-center gap-2">
          <Settings2 className="h-4 w-4 text-slate-400" />
          <h3 className="text-base font-semibold text-white">
            Review Settings
          </h3>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 p-3 sm:p-4 rounded-xl bg-slate-900/30 border border-slate-800/50">
          <div className="space-y-2">
            <label className="text-sm font-medium text-slate-300">
              Ensemble Reviews
            </label>
            <select
              value={numReviews}
              onChange={(e) => setNumReviews(Number(e.target.value))}
              className="input-field"
            >
              {[1, 2, 3, 4, 5].map((n) => (
                <option key={n} value={n}>
                  {n} review{n > 1 ? "s" : ""}
                </option>
              ))}
            </select>
            <p className="text-xs text-slate-500">
              More reviews improve accuracy
            </p>
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium text-slate-300">
              Reflection Rounds
            </label>
            <select
              value={numReflections}
              onChange={(e) => setNumReflections(Number(e.target.value))}
              className="input-field"
            >
              {[1, 2, 3].map((n) => (
                <option key={n} value={n}>
                  {n} round{n > 1 ? "s" : ""}
                </option>
              ))}
            </select>
            <p className="text-xs text-slate-500">Self-reflection iterations</p>
          </div>
        </div>
      </div>

      {/* Error Message */}
      {error && (
        <div className="flex items-center gap-2 p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400">
          <AlertCircle className="h-5 w-5 shrink-0" />
          <p className="text-sm">{error}</p>
        </div>
      )}

      {/* Submit Button */}
      <Button
        onClick={handleSubmit}
        disabled={!file || !model || isUploading}
        className="w-full btn-primary-gradient h-12 text-base"
      >
        {isUploading ? (
          <>
            <Loader2 className="h-5 w-5 animate-spin mr-2" />
            Uploading...
          </>
        ) : (
          "Start Review"
        )}
      </Button>
    </div>
  );
}
