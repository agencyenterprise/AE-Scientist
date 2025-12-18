"use client";

/**
 * Authentication context provider.
 *
 * Manages authentication state across the entire application.
 */

import { createContext, useContext, useEffect, useState, useCallback, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import type { AuthContextValue, AuthState } from "@/types/auth";
import * as authApi from "@/shared/lib/auth-api";
import { clearSessionToken, getSessionToken, setSessionToken } from "@/shared/lib/session-token";

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

interface AuthProviderProps {
  children: React.ReactNode;
}

function AuthProviderInner({ children }: AuthProviderProps) {
  const router = useRouter();
  const searchParams = useSearchParams();

  const [authState, setAuthState] = useState<AuthState>({
    isAuthenticated: false,
    isLoading: true,
    user: null,
    error: null,
  });

  const checkAuthStatus = useCallback(async () => {
    const token = getSessionToken();
    if (!token) {
      setAuthState({
        isAuthenticated: false,
        isLoading: false,
        user: null,
        error: null,
      });
      return;
    }

    try {
      setAuthState(prev => ({ ...prev, isLoading: true, error: null }));

      const authStatus = await authApi.checkAuthStatus();

      if (authStatus.authenticated && authStatus.user) {
        setAuthState({
          isAuthenticated: true,
          isLoading: false,
          user: authStatus.user,
          error: null,
        });
        return;
      }

      clearSessionToken();
      setAuthState({
        isAuthenticated: false,
        isLoading: false,
        user: null,
        error: null,
      });
    } catch {
      clearSessionToken();
      setAuthState({
        isAuthenticated: false,
        isLoading: false,
        user: null,
        error: "Failed to check authentication status",
      });
    }
  }, []);

  // Handle login redirect
  const login = () => {
    authApi.login();
  };

  // Handle logout
  const logout = async () => {
    try {
      setAuthState(prev => ({ ...prev, isLoading: true, error: null }));

      clearSessionToken();
      const success = await authApi.logout();

      if (success) {
        setAuthState({
          isAuthenticated: false,
          isLoading: false,
          user: null,
          error: null,
        });

        // Redirect to login page
        router.push("/login");
      } else {
        setAuthState(prev => ({
          ...prev,
          isLoading: false,
          error: "Logout failed",
        }));
      }
    } catch {
      clearSessionToken();
      setAuthState(prev => ({
        ...prev,
        isLoading: false,
        error: "Logout failed",
      }));
    }
  };

  // Initialize auth - check for OAuth errors and auth status on mount
  const readTokenFromHash = (): string | null => {
    if (typeof window === "undefined") {
      return null;
    }
    const hash = window.location.hash.startsWith("#")
      ? window.location.hash.slice(1)
      : window.location.hash;
    if (!hash) {
      return null;
    }
    const params = new URLSearchParams(hash);
    return params.get("token");
  };

  const clearTokenParams = (): void => {
    if (typeof window === "undefined") {
      return;
    }
    const url = new URL(window.location.href);
    if (url.searchParams.has("token")) {
      url.searchParams.delete("token");
    }
    if (url.hash) {
      const hashValue = url.hash.startsWith("#") ? url.hash.slice(1) : url.hash;
      if (hashValue) {
        const hashParams = new URLSearchParams(hashValue);
        if (hashParams.has("token")) {
          hashParams.delete("token");
          const nextHash = hashParams.toString();
          url.hash = nextHash ? `#${nextHash}` : "";
        }
      }
    }
    window.history.replaceState({}, "", url.toString());
  };

  useEffect(() => {
    const initAuth = async () => {
      // Check for OAuth callback errors in URL
      const error = searchParams.get("error");
      if (error) {
        clearSessionToken();
        let errorMessage = "Authentication failed";

        switch (error) {
          case "oauth_cancelled":
            errorMessage = "Login was cancelled. Please try again if you want to sign in.";
            break;
          case "oauth_error":
            errorMessage = "OAuth authentication failed";
            break;
          case "auth_failed":
            errorMessage = "Authentication failed";
            break;
          case "server_error":
            errorMessage = "Server error during authentication";
            break;
          default:
            errorMessage = `Authentication error: ${error}`;
        }

        setAuthState({
          isAuthenticated: false,
          isLoading: false,
          user: null,
          error: errorMessage,
        });
        return;
      }

      const tokenFromQuery = searchParams.get("token");
      const tokenFromHash = readTokenFromHash();
      const incomingToken = tokenFromQuery || tokenFromHash;
      if (incomingToken) {
        setSessionToken(incomingToken);
        clearTokenParams();
      }

      // No error - check auth status
      await checkAuthStatus();
    };

    void initAuth();
  }, [searchParams, checkAuthStatus]);

  const contextValue: AuthContextValue = {
    ...authState,
    login,
    logout,
    checkAuthStatus,
  };

  return <AuthContext.Provider value={contextValue}>{children}</AuthContext.Provider>;
}

export function AuthProvider({ children }: AuthProviderProps) {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen bg-gray-50 flex flex-col justify-center py-12 sm:px-6 lg:px-8">
          <div className="sm:mx-auto sm:w-full sm:max-w-md">
            <div className="flex justify-center">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
            </div>
            <p className="mt-4 text-center text-gray-600">Loading authentication...</p>
          </div>
        </div>
      }
    >
      <AuthProviderInner>{children}</AuthProviderInner>
    </Suspense>
  );
}

export function useAuthContext(): AuthContextValue {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error("useAuthContext must be used within an AuthProvider");
  }
  return context;
}
