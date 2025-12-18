"use client";

/**
 * Utilities for managing the SPA session token.
 */

const TOKEN_STORAGE_KEY = "ae_scientist_session_token";
let inMemoryToken: string | null = null;

function isBrowser(): boolean {
  return typeof window !== "undefined" && typeof window.localStorage !== "undefined";
}

export function getSessionToken(): string | null {
  if (isBrowser()) {
    try {
      const value = window.localStorage.getItem(TOKEN_STORAGE_KEY);
      inMemoryToken = value;
      return value;
    } catch {
      return inMemoryToken;
    }
  }

  return inMemoryToken;
}

export function setSessionToken(token: string): void {
  if (isBrowser()) {
    try {
      window.localStorage.setItem(TOKEN_STORAGE_KEY, token);
    } catch {
      // Ignore storage quota errors and fall back to in-memory token
    }
  }

  inMemoryToken = token;
}

export function clearSessionToken(): void {
  if (isBrowser()) {
    try {
      window.localStorage.removeItem(TOKEN_STORAGE_KEY);
    } catch {
      // Ignore storage quota errors
    }
  }

  inMemoryToken = null;
}

export function hasSessionToken(): boolean {
  return Boolean(getSessionToken());
}

export function withAuthHeaders(base?: HeadersInit): Headers {
  const headers = new Headers(base || undefined);
  const token = getSessionToken();
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  return headers;
}
