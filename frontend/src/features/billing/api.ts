"use client";

import { api } from "@/shared/lib/api-client-typed";
import type { components } from "@/types/api.gen";

// Use generated types from OpenAPI schema
export type PublicConfig = components["schemas"]["PublicConfigResponse"];
export type CreditTransaction = components["schemas"]["CreditTransactionModel"];
export type WalletResponse = components["schemas"]["BillingWalletResponse"];
export type FundingOption = components["schemas"]["FundingOptionModel"];
export type FundingOptionListResponse = components["schemas"]["FundingOptionListResponse"];

export async function fetchPublicConfig(): Promise<PublicConfig> {
  const { data, error } = await api.GET("/api/public-config");
  if (error) throw new Error("Failed to fetch public config");
  return data;
}

export const TRANSACTION_TYPES = [
  "purchase",
  "debit",
  "refund",
  "adjustment",
  "hold",
  "hold_reversal",
] as const;

export type TransactionType = (typeof TRANSACTION_TYPES)[number];

// Default types to show (excludes hold and hold_reversal)
export const DEFAULT_TRANSACTION_TYPES: TransactionType[] = [
  "purchase",
  "debit",
  "refund",
  "adjustment",
];

export async function fetchWallet(params?: {
  limit?: number;
  offset?: number;
  transactionTypes?: TransactionType[];
}): Promise<WalletResponse> {
  const queryParams: Record<string, unknown> = {
    limit: params?.limit ?? 10,
    offset: params?.offset ?? 0,
  };

  // Only include transaction_types if explicitly provided
  if (params?.transactionTypes && params.transactionTypes.length > 0) {
    queryParams.transaction_types = params.transactionTypes.join(",");
  }

  const { data, error } = await api.GET("/api/billing/wallet", {
    params: { query: queryParams },
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
