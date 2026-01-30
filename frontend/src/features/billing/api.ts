"use client";

import { api } from "@/shared/lib/api-client-typed";

export interface CreditTransaction {
  id: number;
  amount: number;
  transaction_type: string;
  status: string;
  description?: string | null;
  metadata: Record<string, unknown>;
  stripe_session_id?: string | null;
  created_at: string;
}

export interface WalletResponse {
  balance: number;
  transactions: CreditTransaction[];
}

export interface CreditPack {
  price_id: string;
  credits: number;
  currency: string;
  unit_amount: number;
  nickname: string;
}

export interface CreditPackListResponse {
  packs: CreditPack[];
}

export async function fetchWallet(): Promise<WalletResponse> {
  const { data, error } = await api.GET("/api/billing/wallet", {
    params: { query: { limit: 25 } },
  });
  if (error) throw new Error("Failed to fetch wallet");
  return data as WalletResponse;
}

export async function fetchCreditPacks(): Promise<CreditPackListResponse> {
  const { data, error } = await api.GET("/api/billing/packs");
  if (error) throw new Error("Failed to fetch credit packs");
  return data as CreditPackListResponse;
}

export async function createCheckoutSession(payload: {
  price_id: string;
  success_url: string;
  cancel_url: string;
}): Promise<{ checkout_url: string }> {
  const { data, error } = await api.POST("/api/billing/checkout-session", {
    body: payload,
  });
  if (error) throw new Error("Failed to create checkout session");
  return data as { checkout_url: string };
}
