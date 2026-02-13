"use client";

import { useQuery } from "@tanstack/react-query";
import { format } from "date-fns";
import {
  AlertCircle,
  CheckCircle,
  Clock,
  FileText,
  Loader2,
} from "lucide-react";
import { useState } from "react";

import {
  Sheet,
  SheetBody,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/shared/components/ui/sheet";
import { Skeleton } from "@/shared/components/ui/skeleton";
import type { components } from "@/types/api.gen";

import { fetchPaperReview, fetchPaperReviews } from "../api";
import { PaperReviewResult } from "./PaperReviewResult";

type PaperReviewSummary = components["schemas"]["PaperReviewSummary"];
type PaperReviewDetail = components["schemas"]["PaperReviewDetail"];

interface PaperReviewHistoryProps {
  refreshKey?: number;
}

function StatusIcon({ status }: { status: string }) {
  switch (status) {
    case "completed":
      return <CheckCircle className="h-5 w-5 text-green-400" />;
    case "failed":
      return <AlertCircle className="h-5 w-5 text-red-400" />;
    case "processing":
      return <Loader2 className="h-5 w-5 text-sky-400 animate-spin" />;
    default:
      return <Clock className="h-5 w-5 text-slate-400" />;
  }
}

function ReviewCard({
  review,
  onClick,
}: {
  review: PaperReviewSummary;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="w-full text-left p-3 sm:p-4 rounded-lg border border-slate-700 bg-slate-800/30 hover:bg-slate-800/50 transition-colors"
    >
      <div className="flex items-start gap-2 sm:gap-3">
        <StatusIcon status={review.status} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <FileText className="h-4 w-4 text-slate-500 shrink-0 hidden sm:block" />
            <span className="font-medium text-white truncate text-sm sm:text-base">
              {review.original_filename}
            </span>
          </div>
          <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5 text-xs sm:text-sm text-slate-400">
            <span>{format(new Date(review.created_at), "MMM d, yyyy")}</span>
            <span className="hidden sm:inline">•</span>
            <span className="capitalize">{review.status}</span>
            {review.overall && (
              <>
                <span>•</span>
                <span>Score: {review.overall}/10</span>
              </>
            )}
          </div>
          {review.summary && (
            <p className="mt-2 text-xs sm:text-sm text-slate-300 line-clamp-2">
              {review.summary}
            </p>
          )}
        </div>
      </div>
    </button>
  );
}

export function PaperReviewHistory({
  refreshKey = 0,
}: PaperReviewHistoryProps) {
  const [isSheetOpen, setIsSheetOpen] = useState(false);
  const [selectedReview, setSelectedReview] =
    useState<PaperReviewDetail | null>(null);
  const [isLoadingDetail, setIsLoadingDetail] = useState(false);

  const { data, isLoading, error } = useQuery({
    queryKey: ["paper-reviews", refreshKey],
    queryFn: () => fetchPaperReviews({ limit: 20 }),
    refetchInterval: 5000,
  });

  const handleSelectReview = async (reviewId: number) => {
    setIsSheetOpen(true);
    setIsLoadingDetail(true);
    setSelectedReview(null);
    try {
      const detail = await fetchPaperReview(reviewId);
      setSelectedReview(detail);
    } catch {
      // Keep sheet open but show error state
    } finally {
      setIsLoadingDetail(false);
    }
  };

  const handleCloseSheet = () => {
    setIsSheetOpen(false);
    // Delay clearing the review to allow close animation
    setTimeout(() => {
      setSelectedReview(null);
    }, 200);
  };

  if (isLoading) {
    return (
      <div className="space-y-3">
        {[...Array(3)].map((_, i) => (
          <Skeleton key={i} className="h-24 w-full" />
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-center py-8 text-slate-400">
        Failed to load review history
      </div>
    );
  }

  if (!data?.reviews.length) {
    return (
      <div className="text-center py-8">
        <FileText className="h-12 w-12 text-slate-600 mx-auto mb-3" />
        <p className="text-slate-400">No reviews yet</p>
        <p className="text-sm text-slate-500 mt-1">
          Upload a paper to get started
        </p>
      </div>
    );
  }

  return (
    <>
      <div className="space-y-3">
        {data.reviews.map((review) => (
          <ReviewCard
            key={review.id}
            review={review}
            onClick={() => handleSelectReview(review.id)}
          />
        ))}
      </div>

      <Sheet open={isSheetOpen} onOpenChange={handleCloseSheet}>
        <SheetContent className="flex flex-col">
          <SheetHeader>
            <SheetTitle>
              {selectedReview?.original_filename || "Review Details"}
            </SheetTitle>
          </SheetHeader>
          <SheetBody>
            {isLoadingDetail ? (
              <div className="flex items-center justify-center py-12">
                <Loader2 className="h-8 w-8 animate-spin text-sky-500" />
              </div>
            ) : selectedReview ? (
              <PaperReviewResult review={selectedReview} />
            ) : (
              <div className="text-center py-12 text-slate-400">
                Failed to load review details
              </div>
            )}
          </SheetBody>
        </SheetContent>
      </Sheet>
    </>
  );
}
