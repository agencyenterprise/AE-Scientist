/**
 * Authentication API functions.
 *
 * Handles communication with the backend authentication endpoints.
 */

import { config } from "./config";
import { getSessionToken, withAuthHeaders } from "./session-token";
import type { AuthStatus, User } from "@/types/auth";

/**
 * Redirect to login page (handled by Clerk).
 * This function is kept for backward compatibility but login is now handled by Clerk UI.
 */
export function login(): void {
  window.location.href = "/login";
}

/**
 * Log out the current user.
 */
export async function logout(): Promise<boolean> {
  try {
    const response = await fetch(`${config.apiUrl}/auth/logout`, {
      method: "POST",
      headers: withAuthHeaders(new Headers({ "Content-Type": "application/json" })),
    });

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
    const response = await fetch(`${config.apiUrl}/auth/me`, {
      headers: withAuthHeaders(new Headers({ "Content-Type": "application/json" })),
    });

    if (response.ok) {
      const user: User = await response.json();
      return user;
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
    const response = await fetch(`${config.apiUrl}/auth/status`, {
      headers: withAuthHeaders(new Headers({ "Content-Type": "application/json" })),
    });

    if (response.ok) {
      const authStatus: AuthStatus = await response.json();
      return authStatus;
    } else {
      return { authenticated: false };
    }
  } catch {
    return { authenticated: false };
  }
}
