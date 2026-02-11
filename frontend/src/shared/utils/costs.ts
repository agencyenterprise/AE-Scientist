"use client";

import type { components } from "@/types/api.gen";

// Re-export the generated types for convenience
export type InsufficientBalanceError = components["schemas"]["InsufficientBalanceError"];
export type InsufficientBalanceErrorDetail =
  components["schemas"]["InsufficientBalanceErrorDetail"];

/**
 * Extract insufficient balance error details from an API error response.
 * Works with both the typed response (InsufficientBalanceError) and legacy formats.
 */
export function getInsufficientBalanceDetail(
  error: InsufficientBalanceError | unknown
): InsufficientBalanceErrorDetail | null {
  // Handle the properly typed response (has detail field)
  if (error && typeof error === "object" && "detail" in error) {
    const detail = (error as { detail: unknown }).detail;
    if (detail && typeof detail === "object" && "message" in detail) {
      return detail as InsufficientBalanceErrorDetail;
    }
  }
  return null;
}

export function formatCentsAsDollars(cents: number): string {
  return `$${(cents / 100).toFixed(2)}`;
}

/**
 * Format a user-friendly insufficient balance error message.
 * Shows required amount when available.
 */
export function formatInsufficientBalanceMessage(
  detail: InsufficientBalanceErrorDetail | null,
  fallback = "Insufficient balance to continue."
): string {
  if (!detail) {
    return fallback;
  }

  if (detail.required_cents !== undefined) {
    return `Insufficient balance. You need ${formatCentsAsDollars(detail.required_cents)} to start.`;
  }

  return detail.message || fallback;
}
