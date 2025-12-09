"use client";

import { apiFetch } from "@/shared/lib/api-client";

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
  return apiFetch<WalletResponse>("/billing/wallet?limit=25");
}

export async function fetchCreditPacks(): Promise<CreditPackListResponse> {
  return apiFetch<CreditPackListResponse>("/billing/packs");
}

export async function createCheckoutSession(payload: {
  price_id: string;
  success_url: string;
  cancel_url: string;
}): Promise<{ checkout_url: string }> {
  return apiFetch<{ checkout_url: string }>("/billing/checkout-session", {
    method: "POST",
    body: payload,
  });
}
