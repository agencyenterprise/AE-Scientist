"use client";

import { api } from "@/shared/lib/api-client-typed";
import type { components } from "@/types/api.gen";

// Re-export generated type for backwards compatibility
export type PaperReviewDetail = components["schemas"]["PaperReviewDetailResponse"];

export async function fetchPaperReview(reviewId: string): Promise<PaperReviewDetail> {
  const { data, error } = await api.GET("/api/paper-reviews/{review_id}", {
    params: { path: { review_id: Number(reviewId) } },
  });
  if (error) throw new Error("Failed to fetch paper review");
  return data;
}
