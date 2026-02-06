"use client";

import {
  ResearchContext,
  SortDir,
  SortKey,
  DEFAULT_PAGE_SIZE,
} from "@/features/research/contexts/ResearchContext";
import { useCallback, useEffect, useState, useRef } from "react";

import { ProtectedRoute } from "@/shared/components/ProtectedRoute";
import { useVisibilityRefresh } from "@/shared/hooks/useVisibilityRefresh";
import { api } from "@/shared/lib/api-client-typed";
import type { ResearchRun } from "@/shared/lib/api-adapters";
import { convertApiResearchRunList } from "@/shared/lib/api-adapters";
import type { ResearchRunListResponseApi } from "@/types/research";

interface ResearchLayoutProps {
  children: React.ReactNode;
}

export default function ResearchLayout({ children }: ResearchLayoutProps) {
  const [researchRuns, setResearchRuns] = useState<ResearchRun[]>([]);
  const [sortKey, setSortKey] = useState<SortKey>("created");
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  const [isLoading, setIsLoading] = useState(false);

  // Pagination state
  const [currentPage, setCurrentPage] = useState(1);
  const [totalCount, setTotalCount] = useState(0);
  const [pageSize, setPageSizeState] = useState(() => {
    if (typeof window !== "undefined") {
      const saved = localStorage.getItem("research-page-size");
      if (saved) {
        const parsed = parseInt(saved, 10);
        if ([10, 20, 50, 100].includes(parsed)) {
          return parsed;
        }
      }
    }
    return DEFAULT_PAGE_SIZE;
  });

  // Filter state
  const [searchTerm, setSearchTerm] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");

  // Debounce timer ref
  const debounceTimerRef = useRef<NodeJS.Timeout | null>(null);

  const loadResearchRuns = useCallback(async (): Promise<void> => {
    setIsLoading(true);
    try {
      const offset = (currentPage - 1) * pageSize;

      const { data: apiResponse, error } = await api.GET("/api/research-runs/", {
        params: {
          query: {
            limit: pageSize,
            offset: offset,
            search: searchTerm || undefined,
            status: statusFilter && statusFilter !== "all" ? statusFilter : undefined,
          },
        },
      });
      if (error) throw new Error("Failed to load research runs");
      const data = convertApiResearchRunList(apiResponse as unknown as ResearchRunListResponseApi);
      setResearchRuns(data.items);
      setTotalCount(apiResponse.total);
    } catch {
      // silence error in prod/CI
    } finally {
      setIsLoading(false);
    }
  }, [currentPage, pageSize, searchTerm, statusFilter]);

  // Load data when filters or page change
  useEffect(() => {
    loadResearchRuns();
  }, [loadResearchRuns]);

  // Refresh data when user returns to the tab
  useVisibilityRefresh(loadResearchRuns);

  // Reset to page 1 when filters change
  const handleSetSearchTerm = useCallback((term: string) => {
    setSearchTerm(term);
    setCurrentPage(1);
  }, []);

  const handleSetStatusFilter = useCallback((status: string) => {
    setStatusFilter(status);
    setCurrentPage(1);
  }, []);

  const handleSetPageSize = useCallback((size: number) => {
    setPageSizeState(size);
    setCurrentPage(1);
    localStorage.setItem("research-page-size", String(size));
  }, []);

  // Debounced search handler
  const handleDebouncedSearchTerm = useCallback(
    (term: string) => {
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }
      debounceTimerRef.current = setTimeout(() => {
        handleSetSearchTerm(term);
      }, 300);
    },
    [handleSetSearchTerm]
  );

  // Cleanup debounce timer on unmount
  useEffect(() => {
    return () => {
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }
    };
  }, []);

  const researchContextValue = {
    researchRuns,
    refreshResearchRuns: loadResearchRuns,
    sortKey,
    setSortKey,
    sortDir,
    setSortDir,
    // Pagination
    currentPage,
    setCurrentPage,
    totalCount,
    pageSize,
    setPageSize: handleSetPageSize,
    // Filters
    searchTerm,
    setSearchTerm: handleDebouncedSearchTerm,
    statusFilter,
    setStatusFilter: handleSetStatusFilter,
    isLoading,
  };

  return (
    <ProtectedRoute>
      <ResearchContext.Provider value={researchContextValue}>{children}</ResearchContext.Provider>
    </ProtectedRoute>
  );
}
