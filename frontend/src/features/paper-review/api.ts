"use client";

import { api } from "@/shared/lib/api-client-typed";

export interface PaperReviewDetail {
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
  cost_cents?: number;
}

export async function fetchPaperReview(reviewId: string): Promise<PaperReviewDetail> {
  const { data, error } = await api.GET("/api/paper-reviews/{review_id}", {
    params: { path: { review_id: Number(reviewId) } },
  });
  if (error) throw new Error("Failed to fetch paper review");
  return data as PaperReviewDetail;
}
