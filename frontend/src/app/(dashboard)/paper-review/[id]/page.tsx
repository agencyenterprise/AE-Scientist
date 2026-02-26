"use client";

import { useParams, useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { Loader2, ArrowLeft, AlertCircle, Lock } from "lucide-react";
import Link from "next/link";
import { cn } from "@/shared/lib/utils";
import { fetchPaperReview } from "@/features/paper-review/api";
import { PaperReviewResult } from "@/features/paper-review/components/PaperReviewResult";
import { PageCard } from "@/shared/components/PageCard";

export default function PaperReviewDetailPage() {
  const params = useParams();
  const router = useRouter();
  const reviewId = params.id as string;

  const {
    data: reviewData,
    isLoading,
    isPending,
    error,
  } = useQuery({
    queryKey: ["paper-review", reviewId],
    queryFn: () => fetchPaperReview(reviewId),
    enabled: !!reviewId,
  });

  const isNotCompleted = reviewData && reviewData.status !== "completed";
  const isAccessRestricted = reviewData?.access_restricted === true;
  const review = reviewData && !isNotCompleted && !isAccessRestricted ? reviewData : null;

  if (isLoading || isPending) {
    return (
      <PageCard>
        <div className="flex items-center justify-center py-24">
          <Loader2 className="h-8 w-8 animate-spin text-slate-400" />
        </div>
      </PageCard>
    );
  }

  // Handle access restriction - show banner with add credits button
  if (isAccessRestricted && reviewData) {
    return (
      <PageCard>
        <div className="p-4 sm:p-6">
          <button
            onClick={() => router.back()}
            className="mb-4 inline-flex items-center gap-2 text-sm text-slate-400 hover:text-white sm:mb-6"
          >
            <ArrowLeft className="h-4 w-4" />
            Back
          </button>

          <div className="mb-4 sm:mb-6">
            <div className="flex items-center gap-2">
              <h1 className="text-lg font-semibold text-white sm:text-xl">
                {reviewData.original_filename}
              </h1>
              {reviewData.tier && (
                <span
                  className={cn(
                    "rounded px-1.5 py-0.5 text-[10px] font-medium",
                    reviewData.tier === "premium"
                      ? "bg-sky-500/10 text-sky-400"
                      : "bg-amber-500/10 text-amber-400"
                  )}
                >
                  {reviewData.tier === "premium" ? "Premium" : "Standard"}
                </span>
              )}
              {reviewData.conference && (
                <span className="rounded bg-slate-700/50 px-1.5 py-0.5 text-[10px] font-medium text-slate-300">
                  {reviewData.conference === "neurips_2025"
                    ? "NeurIPS 2025"
                    : reviewData.conference === "iclr_2025"
                      ? "ICLR 2025"
                      : "ICML"}
                </span>
              )}
            </div>
            <p className="mt-1 text-xs text-slate-400 sm:text-sm">
              {new Date(reviewData.created_at).toLocaleDateString(undefined, {
                dateStyle: "long",
              })}
            </p>
          </div>

          <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-4 sm:p-6">
            <div className="flex flex-col items-center text-center">
              <Lock className="mb-3 h-10 w-10 text-amber-400 sm:mb-4 sm:h-12 sm:w-12" />
              <p className="text-base font-medium text-white sm:text-lg">Review Results Locked</p>
              <p className="mt-2 max-w-md text-sm text-slate-300">
                {reviewData.access_restricted_reason ||
                  "Your balance is negative. Add credits to view the full review details."}
              </p>
              <Link
                href="/billing"
                className="mt-4 w-full rounded-lg bg-sky-600 px-6 py-2.5 text-sm font-medium text-white transition hover:bg-sky-500 sm:mt-6 sm:w-auto"
              >
                Add Credits
              </Link>
            </div>
          </div>
        </div>
      </PageCard>
    );
  }

  if (error || isNotCompleted || !review) {
    const errorMessage = isNotCompleted
      ? `Review is ${reviewData?.status}`
      : error instanceof Error
        ? error.message
        : "Review not found";

    return (
      <PageCard>
        <div className="p-4 sm:p-6">
          <button
            onClick={() => router.back()}
            className="mb-4 inline-flex items-center gap-2 text-sm text-slate-400 hover:text-white sm:mb-6"
          >
            <ArrowLeft className="h-4 w-4" />
            Back
          </button>
          <div className="flex flex-col items-center justify-center py-8 text-center sm:py-12">
            <AlertCircle className="mb-3 h-10 w-10 text-red-400 sm:mb-4 sm:h-12 sm:w-12" />
            <p className="text-base font-medium text-white sm:text-lg">{errorMessage}</p>
            <p className="mt-2 text-sm text-slate-400">
              The review may have been deleted or you don&apos;t have permission to view it.
            </p>
          </div>
        </div>
      </PageCard>
    );
  }

  return (
    <PageCard>
      <div className="p-4 sm:p-6">
        <button
          onClick={() => router.back()}
          className="mb-4 inline-flex items-center gap-2 text-sm text-slate-400 hover:text-white sm:mb-6"
        >
          <ArrowLeft className="h-4 w-4" />
          Back
        </button>

        <div className="mb-4 sm:mb-6">
          <div className="flex items-center gap-2">
            <h1 className="text-lg font-semibold text-white sm:text-xl">
              {review.original_filename}
            </h1>
            {review.tier && (
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
            )}
            <span className="rounded bg-slate-700/50 px-1.5 py-0.5 text-[10px] font-medium text-slate-300">
              {review.conference === "neurips_2025"
                ? "NeurIPS 2025"
                : review.conference === "iclr_2025"
                  ? "ICLR 2025"
                  : "ICML"}
            </span>
          </div>
          <p className="mt-1 text-xs text-slate-400 sm:text-sm">
            {new Date(review.created_at).toLocaleDateString(undefined, {
              dateStyle: "long",
            })}
          </p>
        </div>

        <PaperReviewResult data={review} />
      </div>
    </PageCard>
  );
}
