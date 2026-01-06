"use client";

import { useCallback, useState } from "react";
import { apiFetch } from "@/shared/lib/api-client";
import type { LlmReviewResponse, LlmReviewNotFoundResponse } from "@/types/research";
import { isReview } from "@/types/research";

interface UseReviewDataOptions {
  runId: string;
  conversationId: number | null;
}

interface UseReviewDataReturn {
  review: LlmReviewResponse | null;
  loading: boolean;
  error: string | null;
  notFound: boolean;
  fetchReview: () => Promise<void>;
  setReview: (review: LlmReviewResponse) => void;
}

/**
 * Hook that manages LLM review data fetching and state
 * Lazy-loads review data only when requested
 */
export function useReviewData({
  runId,
  conversationId,
}: UseReviewDataOptions): UseReviewDataReturn {
  const [review, setReview] = useState<LlmReviewResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notFound, setNotFound] = useState(false);

  const fetchReview = useCallback(async (): Promise<void> => {
    // Skip if already loaded or loading
    if (review || loading || notFound || error) {
      return;
    }

    if (!conversationId) {
      setError("Conversation ID is required");
      return;
    }

    if (!runId) {
      setError("Run ID is required");
      return;
    }

    setLoading(true);
    setError(null);
    setNotFound(false);

    try {
      const response = await apiFetch<LlmReviewResponse | LlmReviewNotFoundResponse>(
        `/conversations/${conversationId}/idea/research-run/${runId}/review`
      );

      if (isReview(response)) {
        setReview(response);
      } else {
        setNotFound(true);
      }
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : "We couldn't load the evaluation. Please try again.";
      setError(errorMessage);
      // eslint-disable-next-line no-console
      console.error("Failed to load evaluation:", err);
    } finally {
      setLoading(false);
    }
  }, [review, loading, notFound, error, runId, conversationId]);

  const setReviewDirectly = useCallback((newReview: LlmReviewResponse) => {
    setReview(newReview);
    setNotFound(false);
    setError(null);
    setLoading(false);
  }, []);

  return {
    review,
    loading,
    error,
    notFound,
    fetchReview,
    setReview: setReviewDirectly,
  };
}
