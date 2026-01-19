"use client";

/**
 * Authentication context provider.
 *
 * Manages authentication state across the entire application.
 */

import { createContext, useContext, useEffect, useState, useCallback, Suspense } from "react";
import { useRouter } from "next/navigation";
import { useAuth as useClerkAuth, useUser } from "@clerk/nextjs";
import type { AuthContextValue, AuthState } from "@/types/auth";
import * as authApi from "@/shared/lib/auth-api";
import { clearSessionToken, getSessionToken, setSessionToken } from "@/shared/lib/session-token";
import { config } from "@/shared/lib/config";
import { LoadingPage } from "../components/LoadingPage";

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

interface AuthProviderProps {
  children: React.ReactNode;
}

function AuthProviderInner({ children }: AuthProviderProps) {
  const router = useRouter();

  // Clerk hooks
  const { isLoaded: clerkLoaded, isSignedIn, getToken, signOut } = useClerkAuth();
  const { user: clerkUser } = useUser();

  const [authState, setAuthState] = useState<AuthState>({
    isAuthenticated: false,
    isLoading: true,
    user: null,
    error: null,
  });

  // Track if we've completed the initial auth check
  const [initialCheckComplete, setInitialCheckComplete] = useState(false);

  // Exchange Clerk session for internal session
  const exchangeClerkSession = useCallback(async () => {
    if (!isSignedIn || !clerkUser) {
      return null;
    }

    try {
      // Get Clerk session token
      const clerkToken = await getToken();
      if (!clerkToken) {
        return null;
      }

      // Exchange for internal session token
      const response = await fetch(`${config.apiUrl}/auth/clerk-session`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${clerkToken}`,
          "Content-Type": "application/json",
        },
      });

      if (!response.ok) {
        throw new Error("Failed to exchange Clerk session");
      }

      const data = await response.json();
      return data.session_token;
    } catch (error) {
      // eslint-disable-next-line no-console
      console.error("Error exchanging Clerk session:", error);
      return null;
    }
  }, [isSignedIn, clerkUser, getToken]);

  const checkAuthStatus = useCallback(async () => {
    if (!clerkLoaded) {
      return;
    }

    try {
      // Check if we already have an internal session token
      const existingToken = getSessionToken();

      if (existingToken) {
        // Try to use existing internal token first
        try {
          const authStatus = await authApi.checkAuthStatus();
          if (authStatus.authenticated && authStatus.user) {
            setAuthState({
              isAuthenticated: true,
              isLoading: false,
              user: authStatus.user,
              error: null,
            });
            setInitialCheckComplete(true);
            return;
          }
          // Token is invalid, clear it
          clearSessionToken();
        } catch {
          // Token check failed, clear it
          clearSessionToken();
        }
      }

      // No valid internal token, check Clerk
      if (!isSignedIn) {
        setAuthState({
          isAuthenticated: false,
          isLoading: false,
          user: null,
          error: null,
        });
        setInitialCheckComplete(true);
        return;
      }

      // User is signed in with Clerk but no internal token, exchange it
      setAuthState(prev => ({ ...prev, isLoading: true, error: null }));

      // Exchange Clerk session for internal token
      const internalToken = await exchangeClerkSession();
      if (!internalToken) {
        throw new Error("Failed to get internal session token");
      }

      // Store internal token
      setSessionToken(internalToken);

      // Verify with backend
      const authStatus = await authApi.checkAuthStatus();

      if (authStatus.authenticated && authStatus.user) {
        setAuthState({
          isAuthenticated: true,
          isLoading: false,
          user: authStatus.user,
          error: null,
        });
        setInitialCheckComplete(true);
        return;
      }

      clearSessionToken();
      setAuthState({
        isAuthenticated: false,
        isLoading: false,
        user: null,
        error: null,
      });
      setInitialCheckComplete(true);
    } catch (error) {
      // eslint-disable-next-line no-console
      console.error("Auth check failed:", error);
      clearSessionToken();
      setAuthState({
        isAuthenticated: false,
        isLoading: false,
        user: null,
        error: "Failed to check authentication status",
      });
      setInitialCheckComplete(true);
    }
  }, [clerkLoaded, isSignedIn, exchangeClerkSession]);

  // Handle login redirect (now redirects to Clerk)
  const login = () => {
    router.push("/login");
  };

  // Handle logout (sign out from both Clerk and internal session)
  const logout = async () => {
    try {
      setAuthState(prev => ({ ...prev, isLoading: true, error: null }));

      clearSessionToken();
      await authApi.logout();

      setAuthState({
        isAuthenticated: false,
        isLoading: false,
        user: null,
        error: null,
      });

      await signOut({
        redirectUrl: "/login",
      });
    } catch {
      clearSessionToken();
      setAuthState(prev => ({
        ...prev,
        isLoading: false,
        error: "Logout failed",
      }));
    }
  };

  // Initialize auth
  useEffect(() => {
    checkAuthStatus();
  }, [checkAuthStatus]);

  const contextValue: AuthContextValue = {
    ...authState,
    login,
    logout,
    checkAuthStatus,
  };

  // Show loading state until initial auth check is complete
  if (!initialCheckComplete) {
    return <AuthLoadingState />;
  }

  return <AuthContext.Provider value={contextValue}>{children}</AuthContext.Provider>;
}

export function AuthProvider({ children }: AuthProviderProps) {
  return (
    <Suspense fallback={<AuthLoadingState />}>
      <AuthProviderInner>{children}</AuthProviderInner>
    </Suspense>
  );
}

function AuthLoadingState() {
  return <LoadingPage />;
}

export function useAuthContext(): AuthContextValue {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error("useAuthContext must be used within an AuthProvider");
  }
  return context;
}
