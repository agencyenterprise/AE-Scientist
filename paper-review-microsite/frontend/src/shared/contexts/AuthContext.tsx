"use client";

import { useAuth as useClerkAuth } from "@clerk/nextjs";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";

import { exchangeClerkSession } from "@/shared/lib/auth-api";
import {
  getSessionToken,
  removeSessionToken,
  setSessionToken,
} from "@/shared/lib/session-token";

interface AuthUser {
  id: number;
  email: string;
  name: string;
}

interface AuthContextValue {
  user: AuthUser | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const { isLoaded, isSignedIn, getToken, signOut } = useClerkAuth();
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Exchange Clerk token for internal session token
  useEffect(() => {
    async function initAuth() {
      if (!isLoaded) return;

      if (!isSignedIn) {
        setUser(null);
        setIsLoading(false);
        removeSessionToken();
        return;
      }

      // Check if we already have a valid session token
      const existingToken = getSessionToken();
      if (existingToken) {
        // We could verify the token here, but for simplicity we'll trust it
        setIsLoading(false);
        return;
      }

      try {
        // Get Clerk token and exchange for internal session
        const clerkToken = await getToken();
        if (!clerkToken) {
          setIsLoading(false);
          return;
        }

        const result = await exchangeClerkSession(clerkToken);
        if (result) {
          setSessionToken(result.session_token);
          setUser(result.user);
        }
      } catch (error) {
        // eslint-disable-next-line no-console
        console.error("Failed to initialize auth:", error);
      } finally {
        setIsLoading(false);
      }
    }

    initAuth();
  }, [isLoaded, isSignedIn, getToken]);

  const logout = useCallback(async () => {
    removeSessionToken();
    setUser(null);
    await signOut();
  }, [signOut]);

  return (
    <AuthContext.Provider
      value={{
        user,
        isLoading,
        isAuthenticated: !!user || !!getSessionToken(),
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuthContext() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error("useAuthContext must be used within an AuthProvider");
  }
  return context;
}
