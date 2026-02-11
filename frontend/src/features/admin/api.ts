"use client";

import { api } from "@/shared/lib/api-client-typed";
import type { components } from "@/types/api.gen";

// Use generated types from OpenAPI schema
export type UserWithBalance = components["schemas"]["UserWithBalanceModel"];
export type UserListWithBalancesResponse = components["schemas"]["UserListWithBalancesResponse"];
export type AddCreditRequest = components["schemas"]["AddCreditRequest"];
export type AddCreditResponse = components["schemas"]["AddCreditResponse"];
export type CreatePendingCreditRequest = components["schemas"]["CreatePendingCreditRequest"];
export type PendingCredit = components["schemas"]["PendingCreditModel"];
export type PendingCreditsListResponse = components["schemas"]["PendingCreditsListResponse"];

export async function fetchUsersWithBalances(params?: {
  limit?: number;
  offset?: number;
  search?: string;
}): Promise<UserListWithBalancesResponse> {
  const { data, error } = await api.GET("/api/admin/users", {
    params: {
      query: {
        limit: params?.limit ?? 100,
        offset: params?.offset ?? 0,
        search: params?.search,
      },
    },
  });
  if (error) throw new Error("Failed to fetch users");
  return data;
}

export async function addCreditToUser(payload: AddCreditRequest): Promise<AddCreditResponse> {
  const { data, error } = await api.POST("/api/admin/credits/add", {
    body: payload,
  });
  if (error) throw new Error("Failed to add credit");
  return data;
}

export async function createPendingCredit(
  payload: CreatePendingCreditRequest
): Promise<PendingCredit> {
  const { data, error } = await api.POST("/api/admin/credits/pending", {
    body: payload,
  });
  if (error) throw new Error("Failed to create pending credit");
  return data;
}

export async function fetchPendingCredits(params?: {
  include_claimed?: boolean;
  limit?: number;
  offset?: number;
}): Promise<PendingCreditsListResponse> {
  const { data, error } = await api.GET("/api/admin/credits/pending", {
    params: {
      query: {
        include_claimed: params?.include_claimed ?? false,
        limit: params?.limit ?? 100,
        offset: params?.offset ?? 0,
      },
    },
  });
  if (error) throw new Error("Failed to fetch pending credits");
  return data;
}
