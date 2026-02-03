"use client";

import { api } from "@/shared/lib/api-client-typed";
import type { components } from "@/types/api.gen";

export type PublicConfig = components["schemas"]["PublicConfigResponse"];

export async function fetchPublicConfig(): Promise<PublicConfig> {
  const { data, error } = await api.GET("/api/public-config");
  if (error) throw new Error("Failed to fetch public config");
  return data;
}

export interface CreditTransaction {
  id: number;
  amount_cents: number;
  transaction_type: string;
  status: string;
  description?: string | null;
  metadata: Record<string, unknown>;
  stripe_session_id?: string | null;
  created_at: string;
}

export interface WalletResponse {
  balance_cents: number;
  transactions: CreditTransaction[];
}

export interface FundingOption {
  price_id: string;
  amount_cents: number;
  currency: string;
  unit_amount: number;
  nickname: string;
}

export interface FundingOptionListResponse {
  options: FundingOption[];
}

export async function fetchWallet(): Promise<WalletResponse> {
  const { data, error } = await api.GET("/api/billing/wallet", {
    params: { query: { limit: 25 } },
  });
  if (error) throw new Error("Failed to fetch wallet");
  return data as WalletResponse;
}

export async function fetchFundingOptions(): Promise<FundingOptionListResponse> {
  const { data, error } = await api.GET("/api/billing/packs");
  if (error) throw new Error("Failed to fetch funding options");
  return data as FundingOptionListResponse;
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
