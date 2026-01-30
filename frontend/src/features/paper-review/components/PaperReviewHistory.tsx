"use client";

import { useEffect, useState } from "react";
import { Loader2, FileText, CheckCircle, XCircle, HelpCircle, ChevronRight } from "lucide-react";
import { formatDistanceToNow } from "date-fns";

// Manual types until API types are properly generated
interface PaperReviewSummary {
  id: number;
  summary: string;
  overall: number;
  decision: string;
  original_filename: string;
  model: string;
  created_at: string;
}

interface PaperReviewListResponse {
  reviews: PaperReviewSummary[];
  count: number;
}

function getDecisionIcon(decision: string) {
  const d = decision.toLowerCase();
  if (d.includes("accept")) return <CheckCircle className="h-4 w-4 text-emerald-400" />;
  if (d.includes("reject")) return <XCircle className="h-4 w-4 text-red-400" />;
  return <HelpCircle className="h-4 w-4 text-amber-400" />;
}

function getDecisionColor(decision: string): string {
  const d = decision.toLowerCase();
  if (d.includes("accept")) return "text-emerald-400";
  if (d.includes("reject")) return "text-red-400";
  return "text-amber-400";
}

function getScoreColor(score: number): string {
  if (score >= 7) return "text-emerald-400";
  if (score >= 5) return "text-amber-400";
  return "text-red-400";
}

export function PaperReviewHistory() {
  const [reviews, setReviews] = useState<PaperReviewSummary[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchReviews() {
      try {
        const response = await fetch("/api/paper-reviews?limit=20", {
          credentials: "include",
        });

        if (!response.ok) {
          throw new Error("Failed to fetch reviews");
        }

        const data: PaperReviewListResponse = await response.json();
        setReviews(data.reviews);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load reviews");
      } finally {
        setIsLoading(false);
      }
    }

    fetchReviews();
  }, []);

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
      {reviews.map(review => (
        <div
          key={review.id}
          className="flex items-center gap-4 py-4 transition-colors hover:bg-slate-800/30"
        >
          <div className="flex-shrink-0">{getDecisionIcon(review.decision)}</div>

          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <span className="truncate font-medium text-white">{review.original_filename}</span>
              <span className={`text-sm ${getDecisionColor(review.decision)}`}>
                {review.decision}
              </span>
            </div>
            <p className="mt-1 line-clamp-1 text-sm text-slate-400">{review.summary}</p>
            <div className="mt-1 flex items-center gap-3 text-xs text-slate-500">
              <span>
                Score: <span className={getScoreColor(review.overall)}>{review.overall}/10</span>
              </span>
              <span>{review.model.split("/").pop()}</span>
              <span>{formatDistanceToNow(new Date(review.created_at), { addSuffix: true })}</span>
            </div>
          </div>

          <ChevronRight className="h-5 w-5 flex-shrink-0 text-slate-600" />
        </div>
      ))}
    </div>
  );
}
