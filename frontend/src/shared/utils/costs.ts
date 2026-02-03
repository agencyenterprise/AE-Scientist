"use client";

export interface InsufficientBalanceInfo {
  message: string;
  required_cents?: number;
  available_cents?: number;
  action?: string;
}

export function parseInsufficientBalanceError(data: unknown): InsufficientBalanceInfo | null {
  const detail = (data as { detail?: unknown } | undefined)?.detail ?? data;

  if (typeof detail === "string") {
    return { message: detail };
  }

  if (typeof detail === "object" && detail !== null) {
    const payload = detail as Record<string, unknown>;
    const message =
      typeof payload.message === "string"
        ? payload.message
        : "Insufficient balance. Please add funds to continue.";
    return {
      message,
      required_cents:
        typeof payload.required_cents === "number" ? payload.required_cents : undefined,
      available_cents:
        typeof payload.available_cents === "number" ? payload.available_cents : undefined,
      action: typeof payload.action === "string" ? payload.action : undefined,
    };
  }

  return null;
}

export function formatCentsAsDollars(cents: number): string {
  return `$${(cents / 100).toFixed(2)}`;
}
