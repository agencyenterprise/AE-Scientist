/**
 * Authentication API functions.
 *
 * Handles communication with the backend authentication endpoints.
 */

import { config } from "./config";
import type { AuthStatus, User } from "@/types/auth";

/**
 * Redirect to Google OAuth login.
 */
export function login(): void {
  window.location.href = `${config.apiUrl}/auth/login`;
}

/**
 * Log out the current user.
 */
export async function logout(): Promise<boolean> {
  try {
    const response = await fetch(`${config.apiUrl}/auth/logout`, {
      method: "POST",
      credentials: "include", // Include cookies
      headers: {
        "Content-Type": "application/json",
      },
    });

    if (response.ok) {
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
  try {
    const response = await fetch(`${config.apiUrl}/auth/me`, {
      credentials: "include", // Include cookies
      headers: {
        "Content-Type": "application/json",
      },
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
  try {
    const response = await fetch(`${config.apiUrl}/auth/status`, {
      credentials: "include", // Include cookies
      headers: {
        "Content-Type": "application/json",
      },
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
