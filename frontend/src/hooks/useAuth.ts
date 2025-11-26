/**
 * Custom hook for authentication.
 *
 * Provides easy access to authentication state and functions.
 */

import { useAuthContext } from "@/contexts/AuthContext";
import type { AuthContextValue } from "@/types/auth";

export function useAuth(): AuthContextValue {
  return useAuthContext();
}
