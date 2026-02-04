"use client";

import { useAuth } from "@/shared/hooks/useAuth";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchWallet } from "@/features/billing/api";
import { useEffect, useRef } from "react";
import { apiStream } from "@/shared/lib/api-client";
import type { WalletStreamEvent } from "@/types";

interface WalletBalanceResult {
  balance_cents: number;
  balanceDollars: number;
  isLoading: boolean;
  refetch: () => Promise<unknown>;
}

export function useWalletBalance(): WalletBalanceResult {
  const { isAuthenticated } = useAuth();
  const queryClient = useQueryClient();
  const reconnectAttemptsRef = useRef(0);
  const abortControllerRef = useRef<AbortController | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const { data, isLoading, refetch } = useQuery({
    queryKey: ["billing", "wallet-balance"],
    queryFn: () => fetchWallet({ limit: 1 }), // Only need balance, minimal transactions
    staleTime: 30_000,
    enabled: isAuthenticated,
  });

  useEffect(() => {
    if (!isAuthenticated) {
      return () => undefined;
    }

    const connect = async () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      const controller = new AbortController();
      abortControllerRef.current = controller;
      try {
        const response = await apiStream("/billing/wallet/stream", {
          headers: { Accept: "text/event-stream" },
          signal: controller.signal,
        });
        if (!response.body) {
          throw new Error("No response body");
        }
        reconnectAttemptsRef.current = 0;
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n\n");
          buffer = lines.pop() || "";
          for (const line of lines) {
            if (!line.startsWith("data: ")) continue;
            try {
              const evt = JSON.parse(line.slice(6)) as WalletStreamEvent;
              if (evt.type === "balance" && typeof evt.data.balance_cents === "number") {
                const balance_cents = evt.data.balance_cents;
                queryClient.setQueryData<{ balance_cents: number } | undefined>(
                  ["billing", "wallet-balance"],
                  prev => ({ ...(prev ?? {}), balance_cents })
                );
                queryClient.setQueryData<
                  { balance_cents: number; transactions?: unknown[] } | undefined
                >(["billing", "wallet"], prev => ({
                  ...(prev ?? { transactions: [] }),
                  balance_cents,
                }));
              }
            } catch {
              // ignore malformed lines
            }
          }
        }
      } catch (err) {
        if ((err as Error).name === "AbortError") {
          return;
        }
        const attempts = reconnectAttemptsRef.current;
        if (attempts < 5) {
          const delay = Math.min(1000 * 2 ** attempts, 15000);
          reconnectAttemptsRef.current = attempts + 1;
          reconnectTimeoutRef.current = setTimeout(connect, delay);
        }
      }
    };

    connect();

    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
    };
  }, [isAuthenticated, queryClient]);

  const balance_cents = data?.balance_cents ?? 0;

  return {
    balance_cents,
    balanceDollars: balance_cents / 100,
    isLoading,
    refetch: () => refetch(),
  };
}
