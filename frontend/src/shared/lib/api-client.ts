/**
 * Centralized API client with error handling.
 *
 * Provides fetch wrappers that throw typed errors with HTTP status codes,
 * enabling global 401 handling in QueryProvider.
 */

import { config } from "./config";

/**
 * Custom error class that carries HTTP status codes.
 * Used by QueryProvider's global error handler to detect 401s.
 */
export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public data?: unknown
  ) {
    super(message);
    this.name = "ApiError";
  }
}

interface ApiFetchOptions extends Omit<RequestInit, "body"> {
  /** Skip JSON parsing (for non-JSON responses) */
  skipJson?: boolean;
  /** Request body - will be JSON.stringify'd if object */
  body?: RequestInit["body"] | object;
}

/**
 * Type-safe fetch wrapper for API requests.
 *
 * - Automatically includes credentials for cookie-based auth
 * - Sets Content-Type header for JSON requests
 * - Throws ApiError with status code on non-ok responses
 *
 * @param path - API path (will be prefixed with config.apiUrl). Can include query strings.
 * @param options - Fetch options with additional skipJson flag
 * @returns Parsed JSON response (or undefined if skipJson)
 * @throws ApiError on non-ok responses
 *
 * @example
 * ```ts
 * // GET request
 * const data = await apiFetch<LLMDefaultsResponse>('/llm-defaults/idea_generation');
 *
 * // GET with query params
 * const results = await apiFetch<SearchResponse>('/search?q=test&limit=20');
 *
 * // POST with body
 * const result = await apiFetch<Response>('/endpoint', {
 *   method: 'POST',
 *   body: { key: 'value' }
 * });
 * ```
 */
export async function apiFetch<T>(path: string, options?: ApiFetchOptions): Promise<T> {
  const { skipJson, body, ...fetchOptions } = options || {};

  // For FormData, don't set Content-Type (let browser set it with boundary)
  const isFormData = body instanceof FormData;
  const headers: HeadersInit = isFormData
    ? { ...fetchOptions.headers }
    : { "Content-Type": "application/json", ...fetchOptions.headers };

  const response = await fetch(buildRequestUrl(path), {
    ...fetchOptions,
    credentials: "include",
    headers,
    body:
      body && typeof body === "object" && !isFormData
        ? JSON.stringify(body)
        : (body as RequestInit["body"]),
  });

  if (!response.ok) {
    // Auto-redirect to login on 401 (session expired)
    if (response.status === 401) {
      window.location.href = "/login";
    }
    const errorData = await parseErrorResponse(response);
    throw new ApiError(response.status, `HTTP ${response.status}`, errorData);
  }

  if (skipJson) {
    return undefined as T;
  }

  return response.json();
}

/**
 * Fetch wrapper for streaming SSE endpoints.
 *
 * Returns the raw Response object for streaming, but throws ApiError on auth failures.
 * Use this for endpoints that return Server-Sent Events or streaming responses.
 *
 * @param path - API path (will be prefixed with config.apiUrl)
 * @param options - Standard fetch options
 * @returns Raw Response object for streaming
 * @throws ApiError on non-ok responses
 *
 * @example
 * ```ts
 * const response = await apiStream('/conversations/import/manual', {
 *   method: 'POST',
 *   body: JSON.stringify(data),
 *   headers: { Accept: 'text/event-stream' }
 * });
 * const reader = response.body.getReader();
 * ```
 */
export async function apiStream(path: string, options?: RequestInit): Promise<Response> {
  const response = await fetch(buildRequestUrl(path), {
    ...options,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });

  if (!response.ok) {
    // Auto-redirect to login on 401 (session expired)
    if (response.status === 401) {
      window.location.href = "/login";
    }
    const errorData = await parseErrorResponse(response);
    throw new ApiError(response.status, `HTTP ${response.status}`, errorData);
  }

  return response;
}

function buildRequestUrl(path: string): string {
  const url = `${config.apiUrl}${path}`;

  if (typeof window === "undefined" || window.location.protocol !== "https:") {
    return url;
  }

  try {
    const parsedUrl = new URL(url);

    if (parsedUrl.protocol === "http:" && parsedUrl.hostname.endsWith(".railway.app")) {
      parsedUrl.protocol = "https:";
      return parsedUrl.toString();
    }

    return parsedUrl.toString();
  } catch {
    return url;
  }
}

async function parseErrorResponse(response: Response): Promise<unknown> {
  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    try {
      return await response.json();
    } catch {
      return undefined;
    }
  }
  try {
    return await response.text();
  } catch {
    return undefined;
  }
}
