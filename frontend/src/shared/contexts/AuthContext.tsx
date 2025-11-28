"use client";

/**
 * Authentication context provider.
 *
 * Manages authentication state across the entire application.
 */

import { createContext, useContext, useEffect, useState, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import type { AuthContextValue, AuthState } from "@/types/auth";
import * as authApi from "@/shared/lib/auth-api";

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

  // Check authentication status on mount
  const checkAuthStatus = async () => {
    try {
      setAuthState(prev => ({ ...prev, isLoading: true, error: null }));

      const authStatus = await authApi.checkAuthStatus();

      setAuthState({
        isAuthenticated: authStatus.authenticated,
        isLoading: false,
        user: authStatus.user || null,
        error: null,
      });
    } catch {
      // Swallow console in production CI; capture error in state only
      setAuthState({
        isAuthenticated: false,
        isLoading: false,
        user: null,
        error: "Failed to check authentication status",
      });
    }
  };

  // Handle login redirect
  const login = () => {
    authApi.login();
  };

  // Handle logout
  const logout = async () => {
    try {
      setAuthState(prev => ({ ...prev, isLoading: true, error: null }));

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
      // Avoid console noise in CI; show in UI state instead
      setAuthState(prev => ({
        ...prev,
        isLoading: false,
        error: "Logout failed",
      }));
    }
  };

  // Check for OAuth callback errors
  useEffect(() => {
    const error = searchParams.get("error");
    if (error) {
      let errorMessage = "Authentication failed";

      switch (error) {
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

      setAuthState(prev => ({
        ...prev,
        error: errorMessage,
        isLoading: false,
      }));
    }
  }, [searchParams]);

  // Check auth status on mount
  useEffect(() => {
    checkAuthStatus();
  }, []);

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
