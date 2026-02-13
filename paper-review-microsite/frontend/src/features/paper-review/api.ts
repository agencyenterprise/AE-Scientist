import type { components } from "@/types/api.gen";
import { config } from "@/shared/lib/config";
import { getSessionToken } from "@/shared/lib/session-token";

type PaperReviewDetail = components["schemas"]["PaperReviewDetail"];
type PaperReviewListResponse = components["schemas"]["PaperReviewListResponse"];
type PendingReviewsResponse = components["schemas"]["PendingReviewsResponse"];
type ModelsResponse = components["schemas"]["ModelsResponse"];
type PaperDownloadResponse = components["schemas"]["PaperDownloadResponse"];

/**
 * Fetch available models for paper reviews.
 */
export async function fetchModels(): Promise<ModelsResponse> {
  const token = getSessionToken();
  const response = await fetch(`${config.apiUrl}/models`, {
    headers: {
      ...(token && { Authorization: `Bearer ${token}` }),
    },
  });

  if (!response.ok) {
    throw new Error("Failed to fetch models");
  }

  return response.json();
}

/**
 * Submit a paper for review.
 */
export async function submitPaperReview(params: {
  file: File;
  model: string;
  numReviewsEnsemble: number;
  numReflections: number;
}): Promise<{ review_id: number; status: string }> {
  const token = getSessionToken();
  if (!token) {
    throw new Error("Not authenticated");
  }

  const formData = new FormData();
  formData.append("file", params.file);
  formData.append("model", params.model);
  formData.append("num_reviews_ensemble", params.numReviewsEnsemble.toString());
  formData.append("num_reflections", params.numReflections.toString());

  const response = await fetch(`${config.apiUrl}/paper-reviews`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
    },
    body: formData,
  });

  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ detail: "Unknown error" }));
    throw new Error(error.detail || "Failed to submit paper review");
  }

  return response.json();
}

/**
 * Fetch a paper review by ID.
 */
export async function fetchPaperReview(
  reviewId: number,
): Promise<PaperReviewDetail> {
  const token = getSessionToken();
  if (!token) {
    throw new Error("Not authenticated");
  }

  const response = await fetch(`${config.apiUrl}/paper-reviews/${reviewId}`, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    throw new Error("Failed to fetch paper review");
  }

  return response.json();
}

/**
 * Fetch list of paper reviews.
 */
export async function fetchPaperReviews(params?: {
  limit?: number;
  offset?: number;
}): Promise<PaperReviewListResponse> {
  const token = getSessionToken();
  if (!token) {
    throw new Error("Not authenticated");
  }

  const searchParams = new URLSearchParams();
  if (params?.limit) searchParams.set("limit", params.limit.toString());
  if (params?.offset) searchParams.set("offset", params.offset.toString());

  const url = `${config.apiUrl}/paper-reviews${searchParams.toString() ? `?${searchParams}` : ""}`;
  const response = await fetch(url, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    throw new Error("Failed to fetch paper reviews");
  }

  return response.json();
}

/**
 * Fetch pending reviews.
 */
export async function fetchPendingReviews(): Promise<PendingReviewsResponse> {
  const token = getSessionToken();
  if (!token) {
    throw new Error("Not authenticated");
  }

  const response = await fetch(`${config.apiUrl}/paper-reviews/pending`, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    throw new Error("Failed to fetch pending reviews");
  }

  return response.json();
}

/**
 * Get download URL for a paper.
 */
export async function fetchPaperDownloadUrl(
  reviewId: number,
): Promise<PaperDownloadResponse> {
  const token = getSessionToken();
  if (!token) {
    throw new Error("Not authenticated");
  }

  const response = await fetch(
    `${config.apiUrl}/paper-reviews/${reviewId}/download`,
    {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    },
  );

  if (!response.ok) {
    throw new Error("Failed to get download URL");
  }

  return response.json();
}
