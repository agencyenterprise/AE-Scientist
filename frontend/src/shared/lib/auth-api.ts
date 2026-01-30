/**
 * Authentication API functions.
 *
 * Handles communication with the backend authentication endpoints.
 */

import { api } from "./api-client-typed";
import { getSessionToken } from "./session-token";
import type { AuthStatus, User } from "@/types/auth";

/**
 * Log out the current user.
 */
export async function logout(): Promise<boolean> {
  try {
    const { response } = await api.POST("/api/auth/logout");

    if (response.ok || response.status === 401) {
      return true;
    } else {
      return false;
    }
  } catch {
    return false;
  }
}

/**
 * Get current user information.
 */
export async function getCurrentUser(): Promise<User | null> {
  if (!getSessionToken()) {
    return null;
  }

  try {
    const { data, response } = await api.GET("/api/auth/me");

    if (response.ok && data) {
      return data as User;
    } else if (response.status === 401) {
      // Not authenticated
      return null;
    } else {
      return null;
    }
  } catch {
    return null;
  }
}

/**
 * Check authentication status.
 */
export async function checkAuthStatus(): Promise<AuthStatus> {
  if (!getSessionToken()) {
    return { authenticated: false };
  }

  try {
    const { data, response } = await api.GET("/api/auth/status");

    if (response.ok && data) {
      return data as AuthStatus;
    } else {
      return { authenticated: false };
    }
  } catch {
    return { authenticated: false };
  }
}
