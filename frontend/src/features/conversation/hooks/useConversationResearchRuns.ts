"use client";

import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/shared/lib/api-client";
import type { ConversationResponse } from "@/types";
import type {
  ResearchRunSummary,
  UseConversationResearchRunsReturn,
} from "../types/ideation-queue.types";

/**
 * Fetches research runs for a specific conversation.
 * Extracts and sorts runs from the conversation detail response.
 */
async function fetchConversationResearchRuns(
  conversationId: number
): Promise<ResearchRunSummary[]> {
  const data = await apiFetch<ConversationResponse>(`/conversations/${conversationId}`);
  // Sort by created_at descending (newest first)
  return (data.research_runs ?? []).sort(
    (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
  );
}

/**
 * Hook to fetch research runs for a specific conversation.
 * Uses React Query for caching and automatic background refetching.
 *
 * @param conversationId - The ID of the conversation to fetch runs for
 * @returns Object containing runs array, loading state, error, and refetch function
 */
export function useConversationResearchRuns(
  conversationId: number
): UseConversationResearchRunsReturn {
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["conversation-research-runs", conversationId],
    queryFn: () => fetchConversationResearchRuns(conversationId),
    staleTime: 30 * 1000, // 30 seconds - refresh relatively often for status updates
    gcTime: 5 * 60 * 1000, // 5 minutes - keep in cache for re-expansions
  });

  return {
    runs: data ?? [],
    isLoading,
    error:
      error instanceof Error
        ? error.message
        : error
          ? "Couldn't load research runs. Please try again."
          : null,
    refetch,
  };
}
