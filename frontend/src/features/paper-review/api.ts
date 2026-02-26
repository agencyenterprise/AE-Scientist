"use client";

import { api } from "@/shared/lib/api-client-typed";
import type { components } from "@/types/api.gen";

export type AnyPaperReviewDetail =
  | components["schemas"]["NeurIPSPaperReviewDetail"]
  | components["schemas"]["ICLRPaperReviewDetail"]
  | components["schemas"]["ICMLPaperReviewDetail"];

export async function fetchPaperReview(reviewId: string): Promise<AnyPaperReviewDetail> {
  const { data, error } = await api.GET("/api/paper-reviews/{review_id}", {
    params: { path: { review_id: Number(reviewId) } },
  });
  if (error) throw new Error("Failed to fetch paper review");
  return data;
}
