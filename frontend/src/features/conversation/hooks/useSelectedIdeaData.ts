"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/shared/lib/api-client-typed";
import { isErrorResponse } from "@/shared/lib/api-adapters";
import type { Idea } from "@/types";
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
      const { data, error } = await api.GET("/api/conversations/{conversation_id}/idea", {
        params: { path: { conversation_id: conversationId! } },
      });
      // 404 means idea is still being generated - return null, not an error
      const isNotFound = error && "status" in error && error.status === 404;
      if (isNotFound) {
        return null;
      }
      if (error || isErrorResponse(data)) throw new Error("Failed to fetch idea");
      return data.idea;
    },
    // CRITICAL: Disable query when no selection
    enabled: conversationId !== null,
    // Cache settings optimized for read-only preview
    staleTime: 60 * 1000, // 1 minute - idea content is relatively stable
    gcTime: 5 * 60 * 1000, // 5 minutes - keep in cache for re-selections
    // Refetch while idea is being generated (when data is null)
    refetchInterval: query => (query.state.data === null ? 2000 : false),
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
