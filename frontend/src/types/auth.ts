/**
 * Authentication-related TypeScript types.
 */

export interface User {
  id: number;
  email: string;
  name: string;
}

export interface AuthState {
  isAuthenticated: boolean;
  isLoading: boolean;
  user: User | null;
  error: string | null;
}

export interface AuthStatus {
  authenticated: boolean;
  user?: User;
}

export interface AuthContextValue extends AuthState {
  login: () => void;
  logout: () => Promise<void>;
  checkAuthStatus: () => Promise<void>;
}
