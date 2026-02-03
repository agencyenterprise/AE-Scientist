"use client";

import { useParams, useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { Loader2, ArrowLeft, AlertCircle } from "lucide-react";
import { fetchPaperReview, type PaperReviewDetail } from "@/features/paper-review/api";
import {
  PaperReviewResult,
  type PaperReviewResponse,
} from "@/features/paper-review/components/PaperReviewResult";
import { PageCard } from "@/shared/components/PageCard";

function transformToReviewResponse(data: PaperReviewDetail): PaperReviewResponse {
  return {
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
    cost_cents: data.cost_cents || 0,
    original_filename: data.original_filename,
    model: data.model,
    created_at: data.created_at,
  };
}

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
  const review = reviewData && !isNotCompleted ? transformToReviewResponse(reviewData) : null;

  if (isLoading || isPending) {
    return (
      <PageCard>
        <div className="flex items-center justify-center py-24">
          <Loader2 className="h-8 w-8 animate-spin text-slate-400" />
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
        <div className="p-6">
          <button
            onClick={() => router.back()}
            className="mb-6 inline-flex items-center gap-2 text-sm text-slate-400 hover:text-white"
          >
            <ArrowLeft className="h-4 w-4" />
            Back
          </button>
          <div className="flex flex-col items-center justify-center py-12 text-center">
            <AlertCircle className="mb-4 h-12 w-12 text-red-400" />
            <p className="text-lg font-medium text-white">{errorMessage}</p>
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
      <div className="p-6">
        <button
          onClick={() => router.back()}
          className="mb-6 inline-flex items-center gap-2 text-sm text-slate-400 hover:text-white"
        >
          <ArrowLeft className="h-4 w-4" />
          Back
        </button>

        <div className="mb-6">
          <h1 className="text-xl font-semibold text-white">{review.original_filename}</h1>
          <p className="mt-1 text-sm text-slate-400">
            Reviewed with {review.model.split("/").pop()} on{" "}
            {new Date(review.created_at).toLocaleDateString(undefined, {
              dateStyle: "long",
            })}
          </p>
        </div>

        <PaperReviewResult review={review} />
      </div>
    </PageCard>
  );
}
