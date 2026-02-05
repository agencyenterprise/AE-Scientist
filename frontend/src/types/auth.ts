/**
 * Authentication-related TypeScript types.
 */

import type { components } from "./api.gen";

export type User = components["schemas"]["AuthUser"];
export type AuthStatus = components["schemas"]["AuthStatus"];

// Frontend-only types for React context state management
export interface AuthState {
  isAuthenticated: boolean;
  isLoading: boolean;
  user: User | null;
  error: string | null;
}

export interface AuthContextValue extends AuthState {
  login: () => void;
  logout: () => Promise<void>;
  checkAuthStatus: () => Promise<void>;
}
