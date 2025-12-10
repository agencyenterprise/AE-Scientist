"use client";

import { useAuth } from "@/shared/hooks/useAuth";
import { useQuery } from "@tanstack/react-query";
import { fetchWallet } from "@/features/billing/api";

interface WalletBalanceResult {
  balance: number;
  isLoading: boolean;
  refetch: () => Promise<unknown>;
}

export function useWalletBalance(): WalletBalanceResult {
  const { isAuthenticated } = useAuth();

  const { data, isLoading, refetch } = useQuery({
    queryKey: ["billing", "wallet-balance"],
    queryFn: fetchWallet,
    staleTime: 30_000,
    enabled: isAuthenticated,
  });

  return {
    balance: data?.balance ?? 0,
    isLoading,
    refetch: () => refetch(),
  };
}
