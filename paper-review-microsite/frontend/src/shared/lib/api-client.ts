import createClient from "openapi-fetch";

import type { paths } from "@/types/api.gen";

import { config } from "./config";
import { getSessionToken } from "./session-token";

/**
 * Type-safe API client using openapi-fetch.
 * Automatically includes the session token in requests.
 */
export const api = createClient<paths>({
  baseUrl: config.apiBaseUrl,
});

// Add authentication middleware
api.use({
  async onRequest({ request }) {
    const token = getSessionToken();
    if (token) {
      request.headers.set("Authorization", `Bearer ${token}`);
    }
    return request;
  },
  async onResponse({ response }) {
    // Handle 401 responses by redirecting to login
    if (response.status === 401 && typeof window !== "undefined") {
      const pathname = window.location.pathname;
      if (!pathname.startsWith("/login")) {
        window.location.href = "/login";
      }
    }
    return response;
  },
});
