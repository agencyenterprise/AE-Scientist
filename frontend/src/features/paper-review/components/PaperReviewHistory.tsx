"use client";

import * as Sentry from "@sentry/nextjs";
import { useEffect, useState, useRef } from "react";
import {
  Loader2,
  FileText,
  CheckCircle,
  XCircle,
  HelpCircle,
  ChevronRight,
  ChevronDown,
  Clock,
  AlertCircle,
  X,
  Lock,
} from "lucide-react";
import Link from "next/link";
import { formatDistanceToNow } from "date-fns";
import { config } from "@/shared/lib/config";
import { cn } from "@/shared/lib/utils";
import { withAuthHeaders } from "@/shared/lib/session-token";
import { PaperReviewResult, type AnyPaperReviewDetail } from "./PaperReviewResult";
import type { components } from "@/types/api.gen";

// Use generated types from OpenAPI schema
type ReviewDetailResponse = AnyPaperReviewDetail;
type PaperReviewSummary = components["schemas"]["PaperReviewSummary"];
type PaperReviewListResponse = components["schemas"]["PaperReviewListResponse"];

const REFRESH_INTERVAL_MS = 5000; // Refresh every 5 seconds when there are pending reviews

function getStatusIcon(
  status: string,
  decision: string | null | undefined,
  accessRestricted?: boolean
) {
  // Show lock icon for restricted reviews
  if (accessRestricted) {
    return <Lock className="h-4 w-4 text-amber-400" />;
  }

  switch (status) {
    case "pending":
    case "processing":
      return <Clock className="h-4 w-4 animate-pulse text-amber-400" />;
    case "failed":
      return <AlertCircle className="h-4 w-4 text-red-400" />;
    case "completed":
      if (decision) {
        const d = decision.toLowerCase();
        if (d.includes("accept")) return <CheckCircle className="h-4 w-4 text-emerald-400" />;
        if (d.includes("reject")) return <XCircle className="h-4 w-4 text-red-400" />;
      }
      return <HelpCircle className="h-4 w-4 text-amber-400" />;
    default:
      return <HelpCircle className="h-4 w-4 text-slate-400" />;
  }
}

function getStatusText(
  status: string,
  decision: string | null | undefined
): { text: string; color: string } {
  switch (status) {
    case "pending":
      return { text: "Queued", color: "text-amber-400" };
    case "processing":
      return { text: "Analyzing...", color: "text-amber-400" };
    case "failed":
      return { text: "Failed", color: "text-red-400" };
    case "completed":
      if (decision) {
        const d = decision.toLowerCase();
        if (d.includes("accept")) return { text: decision, color: "text-emerald-400" };
        if (d.includes("reject")) return { text: decision, color: "text-red-400" };
        return { text: decision, color: "text-amber-400" };
      }
      return { text: "Completed", color: "text-slate-400" };
    default:
      return { text: status, color: "text-slate-400" };
  }
}

function getOverallMax(conference: string | null | undefined): number {
  if (conference === "neurips_2025") return 6;
  if (conference === "icml") return 5;
  return 10;
}

function getScoreColor(score: number | null | undefined, max: number): string {
  if (score === null || score === undefined) return "text-slate-500";
  const ratio = score / max;
  if (ratio >= 0.75) return "text-emerald-400";
  if (ratio >= 0.5) return "text-amber-400";
  return "text-red-400";
}

interface PaperReviewHistoryProps {
  refreshKey?: number;
}

export function PaperReviewHistory({ refreshKey }: PaperReviewHistoryProps) {
  const [reviews, setReviews] = useState<PaperReviewSummary[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const refreshTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  // State for expanded review
  const [expandedReviewId, setExpandedReviewId] = useState<number | null>(null);
  const [expandedReviewData, setExpandedReviewData] = useState<ReviewDetailResponse | null>(null);
  const [loadingReviewId, setLoadingReviewId] = useState<number | null>(null);

  const fetchReviews = async () => {
    try {
      const headers = withAuthHeaders(new Headers());
      const response = await fetch(`${config.apiUrl}/paper-reviews?limit=20`, {
        headers,
        credentials: "include",
      });

      if (!response.ok) {
        throw new Error("Failed to fetch reviews");
      }

      const data: PaperReviewListResponse = await response.json();
      setReviews(data.reviews);
      return data.reviews;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load reviews");
      return [];
    } finally {
      setIsLoading(false);
    }
  };

  const fetchReviewDetail = async (reviewId: number) => {
    setLoadingReviewId(reviewId);
    try {
      const headers = withAuthHeaders(new Headers());
      const response = await fetch(`${config.apiUrl}/paper-reviews/${reviewId}`, {
        headers,
        credentials: "include",
      });

      if (!response.ok) {
        throw new Error("Failed to fetch review details");
      }

      const data: ReviewDetailResponse = await response.json();

      setExpandedReviewData(data);
      setExpandedReviewId(reviewId);
    } catch (err) {
      Sentry.captureException(err);
    } finally {
      setLoadingReviewId(null);
    }
  };

  const handleReviewClick = (review: PaperReviewSummary) => {
    // Only allow clicking on completed, non-restricted reviews
    if (review.status !== "completed") return;
    if (review.access_restricted) return;

    if (expandedReviewId === review.id) {
      // Collapse if already expanded
      setExpandedReviewId(null);
      setExpandedReviewData(null);
    } else {
      // Fetch and expand
      fetchReviewDetail(review.id);
    }
  };

  useEffect(() => {
    const setupPolling = async () => {
      const fetchedReviews = await fetchReviews();

      // Check if there are any pending/processing reviews
      const hasPendingReviews = fetchedReviews.some(
        r => r.status === "pending" || r.status === "processing"
      );

      // If there are pending reviews, set up auto-refresh
      if (hasPendingReviews) {
        refreshTimeoutRef.current = setTimeout(setupPolling, REFRESH_INTERVAL_MS);
      }
    };

    setupPolling();

    return () => {
      if (refreshTimeoutRef.current) {
        clearTimeout(refreshTimeoutRef.current);
      }
    };
  }, [refreshKey]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-8 w-8 animate-spin text-slate-400" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="py-8 text-center text-slate-400">
        <p>{error}</p>
      </div>
    );
  }

  if (reviews.length === 0) {
    return (
      <div className="py-8 text-center sm:py-12">
        <FileText className="mx-auto mb-3 h-10 w-10 text-slate-600 sm:mb-4 sm:h-12 sm:w-12" />
        <p className="text-slate-400">No paper reviews yet</p>
        <p className="mt-1 text-sm text-slate-500">
          Upload a paper above to get your first AI review
        </p>
      </div>
    );
  }

  return (
    <div className="divide-y divide-slate-700">
      {reviews.map(review => {
        const statusInfo = getStatusText(review.status, review.decision);
        const isInProgress = review.status === "pending" || review.status === "processing";
        const isExpanded = expandedReviewId === review.id;
        const isLoading = loadingReviewId === review.id;
        const isRestricted = review.access_restricted === true;
        const isClickable = review.status === "completed" && !isRestricted;
        const overallMax = getOverallMax(review.conference);

        return (
          <div key={review.id}>
            <div
              onClick={() => handleReviewClick(review)}
              className={`flex items-start gap-3 px-2 py-3 transition-colors sm:items-center sm:gap-4 sm:px-4 sm:py-4 ${
                isInProgress
                  ? "bg-amber-500/5"
                  : isRestricted
                    ? "bg-amber-500/5"
                    : isClickable
                      ? "cursor-pointer hover:bg-slate-800/30"
                      : ""
              }`}
            >
              <div className="mt-0.5 flex-shrink-0 sm:mt-0">
                {getStatusIcon(review.status, review.decision, review.access_restricted)}
              </div>

              <div className="min-w-0 flex-1">
                <div className="flex flex-col gap-0.5 sm:flex-row sm:items-center sm:gap-2">
                  <span className="truncate text-sm font-medium text-white sm:text-base">
                    {review.original_filename}
                  </span>
                  {isRestricted ? (
                    <span className="text-xs text-amber-400 sm:text-sm">Locked</span>
                  ) : (
                    <span className={`text-xs sm:text-sm ${statusInfo.color}`}>
                      {statusInfo.text}
                    </span>
                  )}
                </div>
                {isRestricted ? (
                  <p className="mt-1 text-xs text-amber-400/70 sm:text-sm">
                    Add credits to view this review.
                  </p>
                ) : review.status === "completed" && review.summary ? (
                  <p className="mt-1 line-clamp-1 text-xs text-slate-400 sm:text-sm">
                    {review.summary}
                  </p>
                ) : review.status === "failed" ? (
                  <p className="mt-1 text-xs text-red-400/70 sm:text-sm">Review failed</p>
                ) : isInProgress ? (
                  <div className="mt-1">
                    <p className="text-xs text-amber-400/70 sm:text-sm">
                      {review.progress_step ||
                        (review.status === "pending" ? "Waiting to start..." : "Analyzing...")}
                    </p>
                    {review.progress > 0 && (
                      <div className="mt-1.5 flex items-center gap-2">
                        <div className="h-1.5 w-20 overflow-hidden rounded-full bg-slate-700 sm:w-24">
                          <div
                            className="h-full rounded-full bg-amber-400 transition-all duration-500 ease-out"
                            style={{ width: `${Math.round(review.progress * 100)}%` }}
                          />
                        </div>
                        <span className="text-xs text-slate-500">
                          {Math.round(review.progress * 100)}%
                        </span>
                      </div>
                    )}
                  </div>
                ) : null}
                <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-slate-500 sm:gap-3">
                  {review.status === "completed" && review.overall !== null && !isRestricted && (
                    <span>
                      Score:{" "}
                      <span className={getScoreColor(review.overall, overallMax)}>
                        {review.overall}/{overallMax}
                      </span>
                    </span>
                  )}
                  {review.conference && (
                    <span className="rounded bg-slate-700/50 px-1.5 py-0.5 text-[10px] font-medium text-slate-300">
                      {review.conference === "neurips_2025"
                        ? "NeurIPS 2025"
                        : review.conference === "iclr_2025"
                          ? "ICLR 2025"
                          : "ICML"}
                    </span>
                  )}
                  <span
                    className={cn(
                      "rounded px-1.5 py-0.5 text-[10px] font-medium",
                      review.tier === "premium"
                        ? "bg-sky-500/10 text-sky-400"
                        : "bg-amber-500/10 text-amber-400"
                    )}
                  >
                    {review.tier === "premium" ? "Premium" : "Standard"}
                  </span>
                  <span>
                    {formatDistanceToNow(new Date(review.created_at), { addSuffix: true })}
                  </span>
                </div>
              </div>

              {isLoading && (
                <Loader2 className="h-5 w-5 flex-shrink-0 animate-spin text-slate-400" />
              )}
              {!isLoading &&
                !isInProgress &&
                !isRestricted &&
                isClickable &&
                (isExpanded ? (
                  <ChevronDown className="h-5 w-5 flex-shrink-0 text-slate-400" />
                ) : (
                  <ChevronRight className="hidden h-5 w-5 flex-shrink-0 text-slate-600 sm:block" />
                ))}
              {isRestricted && (
                <Link
                  href="/billing"
                  onClick={e => e.stopPropagation()}
                  className="shrink-0 rounded-lg bg-sky-600 px-2.5 py-1 text-xs font-medium text-white transition-colors hover:bg-sky-500 sm:px-3 sm:py-1.5"
                >
                  Add Credits
                </Link>
              )}
              {isInProgress && (
                <Loader2 className="h-5 w-5 flex-shrink-0 animate-spin text-amber-400" />
              )}
            </div>

            {/* Expanded review content */}
            {isExpanded && expandedReviewData && (
              <div className="border-t border-slate-700/50 bg-slate-800/20 px-2 pb-3 sm:px-4 sm:pb-4">
                <div className="flex justify-end py-2">
                  <button
                    onClick={e => {
                      e.stopPropagation();
                      setExpandedReviewId(null);
                      setExpandedReviewData(null);
                    }}
                    className="flex items-center gap-1 text-xs text-slate-400 hover:text-white"
                  >
                    <X className="h-3 w-3" />
                    Close
                  </button>
                </div>
                <PaperReviewResult data={expandedReviewData} />
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
