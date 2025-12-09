"use client";

export interface InsufficientCreditsInfo {
  message: string;
  required?: number;
  available?: number;
  action?: string;
}

export function parseInsufficientCreditsError(data: unknown): InsufficientCreditsInfo | null {
  const detail = (data as { detail?: unknown } | undefined)?.detail ?? data;

  if (typeof detail === "string") {
    return { message: detail };
  }

  if (typeof detail === "object" && detail !== null) {
    const payload = detail as Record<string, unknown>;
    const message =
      typeof payload.message === "string"
        ? payload.message
        : "Insufficient credits. Please purchase more to continue.";
    return {
      message,
      required: typeof payload.required === "number" ? payload.required : undefined,
      available: typeof payload.available === "number" ? payload.available : undefined,
      action: typeof payload.action === "string" ? payload.action : undefined,
    };
  }

  return null;
}
