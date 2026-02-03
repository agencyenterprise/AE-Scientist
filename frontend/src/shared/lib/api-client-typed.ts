/**
 * Type-safe API client using openapi-fetch.
 *
 * This client enforces that all API calls use valid paths from the OpenAPI spec.
 * Invalid paths will cause TypeScript compile errors, preventing runtime 404s.
 *
 * Usage:
 * ```ts
 * import { api } from "@/shared/lib/api-client-typed";
 *
 * // GET request - path is type-checked
 * const { data, error } = await api.GET("/api/auth/me");
 *
 * // POST with body - both path and body are type-checked
 * const { data, error } = await api.POST("/api/conversations/{conversation_id}/chat", {
 *   params: { path: { conversation_id: 123 } },
 *   body: { message: "Hello" }
 * });
 * ```
 */

import createClient from "openapi-fetch";
import type { paths } from "@/types/api.gen";
import { config } from "./config";
import { getSessionToken } from "./session-token";

/**
 * Type-safe API client instance.
 *
 * All paths are validated against the OpenAPI spec at compile time.
 * Using an invalid path like "/api/foo/bar" will cause a TypeScript error.
 */
export const api = createClient<paths>({
  // Use apiBaseUrl (not apiUrl) because generated paths include /api prefix
  baseUrl: config.apiBaseUrl,
  // Note: Don't set Content-Type here - openapi-fetch handles it automatically:
  // - JSON bodies get "application/json"
  // - FormData gets "multipart/form-data" with proper boundary
});

// Add auth middleware to inject session token
api.use({
  async onRequest({ request }) {
    const token = getSessionToken();
    if (token) {
      request.headers.set("Authorization", `Bearer ${token}`);
    }
    return request;
  },
  async onResponse({ response }) {
    // Auto-redirect to login on 401 (session expired)
    if (response.status === 401 && typeof window !== "undefined") {
      window.location.href = "/login";
    }
    return response;
  },
});

// Re-export types for convenience
export type { paths } from "@/types/api.gen";
