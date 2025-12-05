"use client";

import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/shared/lib/api-client";
import { convertApiResearchRunList } from "@/shared/lib/api-adapters";
import type { ResearchRun, ResearchRunListResponseApi } from "@/types/research";

async function fetchRecentResearch(): Promise<ResearchRun[]> {
  const data = await apiFetch<ResearchRunListResponseApi>("/research-runs/?limit=10");
  const converted = convertApiResearchRunList(data);
  return converted.items;
}

interface UseRecentResearchReturn {
  researchRuns: ResearchRun[];
  isLoading: boolean;
  error: string | null;
  refetch: () => void;
}

/**
 * Hook to fetch the 10 most recent research runs for the current user.
 * Uses React Query for caching and automatic background refetching.
 */
export function useRecentResearch(): UseRecentResearchReturn {
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["recent-research"],
    queryFn: fetchRecentResearch,
    staleTime: 30 * 1000, // 30 seconds - show fresh data often on home page
  });

  return {
    researchRuns: data ?? [],
    isLoading,
    error:
      error instanceof Error ? error.message : error ? "Failed to fetch research history" : null,
    refetch,
  };
}
