import Cookies from "js-cookie";

const SESSION_TOKEN_KEY = "session_token";
const COOKIE_OPTIONS = {
  expires: 7, // 7 days
  secure:
    typeof window !== "undefined" && window.location.protocol === "https:",
  sameSite: "lax" as const,
};

/**
 * Get the session token from cookies.
 */
export function getSessionToken(): string | undefined {
  if (typeof window === "undefined") return undefined;
  return Cookies.get(SESSION_TOKEN_KEY);
}

/**
 * Set the session token in cookies.
 */
export function setSessionToken(token: string): void {
  if (typeof window === "undefined") return;
  Cookies.set(SESSION_TOKEN_KEY, token, COOKIE_OPTIONS);
}

/**
 * Remove the session token from cookies.
 */
export function removeSessionToken(): void {
  if (typeof window === "undefined") return;
  Cookies.remove(SESSION_TOKEN_KEY);
}

/**
 * Check if a session token exists.
 */
export function hasSessionToken(): boolean {
  return !!getSessionToken();
}
