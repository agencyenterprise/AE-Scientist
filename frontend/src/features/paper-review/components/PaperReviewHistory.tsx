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
} from "lucide-react";
import { formatDistanceToNow } from "date-fns";
import { config } from "@/shared/lib/config";
import { withAuthHeaders } from "@/shared/lib/session-token";
import { PaperReviewResult, type PaperReviewResponse } from "./PaperReviewResult";

interface PaperReviewSummary {
  id: number;
  status: string;
  summary: string | null;
  overall: number | null;
  decision: string | null;
  original_filename: string;
  model: string;
  created_at: string;
}

interface PaperReviewListResponse {
  reviews: PaperReviewSummary[];
  count: number;
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

const REFRESH_INTERVAL_MS = 5000; // Refresh every 5 seconds when there are pending reviews

function getStatusIcon(status: string, decision: string | null) {
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

function getStatusText(status: string, decision: string | null): { text: string; color: string } {
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

function getScoreColor(score: number | null): string {
  if (score === null) return "text-slate-500";
  if (score >= 7) return "text-emerald-400";
  if (score >= 5) return "text-amber-400";
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
  const [expandedReviewData, setExpandedReviewData] = useState<PaperReviewResponse | null>(null);
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

      // Transform to PaperReviewResponse format
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

      setExpandedReviewData(result);
      setExpandedReviewId(reviewId);
    } catch (err) {
      Sentry.captureException(err);
    } finally {
      setLoadingReviewId(null);
    }
  };

  const handleReviewClick = (review: PaperReviewSummary) => {
    // Only allow clicking on completed reviews
    if (review.status !== "completed") return;

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
      <div className="py-12 text-center">
        <FileText className="mx-auto mb-4 h-12 w-12 text-slate-600" />
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
        const isClickable = review.status === "completed";

        return (
          <div key={review.id}>
            <div
              onClick={() => handleReviewClick(review)}
              className={`flex items-center gap-4 py-4 transition-colors ${
                isInProgress
                  ? "bg-amber-500/5"
                  : isClickable
                    ? "cursor-pointer hover:bg-slate-800/30"
                    : ""
              }`}
            >
              <div className="flex-shrink-0">{getStatusIcon(review.status, review.decision)}</div>

              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="truncate font-medium text-white">
                    {review.original_filename}
                  </span>
                  <span className={`text-sm ${statusInfo.color}`}>{statusInfo.text}</span>
                </div>
                {review.status === "completed" && review.summary ? (
                  <p className="mt-1 line-clamp-1 text-sm text-slate-400">{review.summary}</p>
                ) : review.status === "failed" ? (
                  <p className="mt-1 text-sm text-red-400/70">Review failed</p>
                ) : isInProgress ? (
                  <p className="mt-1 text-sm text-amber-400/70">
                    {review.status === "pending"
                      ? "Waiting to start..."
                      : "AI is analyzing your paper..."}
                  </p>
                ) : null}
                <div className="mt-1 flex items-center gap-3 text-xs text-slate-500">
                  {review.status === "completed" && review.overall !== null && (
                    <span>
                      Score:{" "}
                      <span className={getScoreColor(review.overall)}>{review.overall}/10</span>
                    </span>
                  )}
                  <span>{review.model.split("/").pop()}</span>
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
                isClickable &&
                (isExpanded ? (
                  <ChevronDown className="h-5 w-5 flex-shrink-0 text-slate-400" />
                ) : (
                  <ChevronRight className="h-5 w-5 flex-shrink-0 text-slate-600" />
                ))}
              {isInProgress && (
                <Loader2 className="h-5 w-5 flex-shrink-0 animate-spin text-amber-400" />
              )}
            </div>

            {/* Expanded review content */}
            {isExpanded && expandedReviewData && (
              <div className="border-t border-slate-700/50 bg-slate-800/20 px-4 pb-4">
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
                <PaperReviewResult review={expandedReviewData} />
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
