import { config } from "./config";

interface AuthUser {
  id: number;
  email: string;
  name: string;
}

interface ClerkSessionResponse {
  session_token: string;
  user: AuthUser;
}

/**
 * Exchange Clerk session token for internal session token.
 */
export async function exchangeClerkSession(
  clerkToken: string,
): Promise<ClerkSessionResponse | null> {
  try {
    const response = await fetch(`${config.apiUrl}/auth/clerk-session`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${clerkToken}`,
        "Content-Type": "application/json",
      },
    });

    if (!response.ok) {
      // eslint-disable-next-line no-console
      console.error("Failed to exchange Clerk session:", response.status);
      return null;
    }

    return await response.json();
  } catch (error) {
    // eslint-disable-next-line no-console
    console.error("Error exchanging Clerk session:", error);
    return null;
  }
}

/**
 * Check authentication status.
 */
export async function checkAuthStatus(
  token: string,
): Promise<{ authenticated: boolean; user: AuthUser | null }> {
  try {
    const response = await fetch(`${config.apiUrl}/auth/status`, {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });

    if (!response.ok) {
      return { authenticated: false, user: null };
    }

    return await response.json();
  } catch {
    return { authenticated: false, user: null };
  }
}

/**
 * Log out the user.
 */
export async function logout(token: string): Promise<void> {
  try {
    await fetch(`${config.apiUrl}/auth/logout`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });
  } catch {
    // Ignore errors during logout
  }
}
