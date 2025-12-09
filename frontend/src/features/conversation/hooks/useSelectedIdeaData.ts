"use client";

import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/shared/lib/api-client";
import type { Idea, IdeaGetResponse } from "@/types";
import type { UseSelectedIdeaDataReturn } from "../types/ideation-queue.types";

/**
 * Fetches idea data for a selected conversation.
 * Returns null when no conversation is selected (conversationId is null).
 * Uses React Query for caching and automatic background refetching.
 *
 * @param conversationId - The ID of the conversation to fetch idea for, or null if none selected
 * @returns Object containing idea data, loading state, error, and refetch function
 */
export function useSelectedIdeaData(conversationId: number | null): UseSelectedIdeaDataReturn {
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["selected-idea", conversationId],
    queryFn: async () => {
      const response = await apiFetch<IdeaGetResponse>(`/conversations/${conversationId}/idea`);
      return response.idea;
    },
    // CRITICAL: Disable query when no selection
    enabled: conversationId !== null,
    // Cache settings optimized for read-only preview
    staleTime: 60 * 1000, // 1 minute - idea content is relatively stable
    gcTime: 5 * 60 * 1000, // 5 minutes - keep in cache for re-selections
  });

  return {
    idea: (data as Idea) ?? null,
    // Only show loading when we have a selection and are actually loading
    isLoading: conversationId !== null && isLoading,
    error:
      error instanceof Error
        ? error.message
        : error
          ? "Couldn't load idea. Please try again."
          : null,
    refetch,
  };
}
