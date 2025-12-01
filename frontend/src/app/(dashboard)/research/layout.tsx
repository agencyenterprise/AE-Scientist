"use client";

import {
  ResearchContext,
  SortDir,
  SortKey,
  DEFAULT_PAGE_SIZE,
} from "@/features/research/contexts/ResearchContext";
import { useCallback, useEffect, useState, useRef } from "react";

import { ProtectedRoute } from "@/shared/components/ProtectedRoute";
import { apiFetch } from "@/shared/lib/api-client";
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
  const [selectedUserId, setSelectedUserId] = useState<number | null>(null);

  // Debounce timer ref
  const debounceTimerRef = useRef<NodeJS.Timeout | null>(null);

  const loadResearchRuns = useCallback(async (): Promise<void> => {
    setIsLoading(true);
    try {
      const offset = (currentPage - 1) * pageSize;
      const params = new URLSearchParams({
        limit: String(pageSize),
        offset: String(offset),
      });

      if (searchTerm) {
        params.set("search", searchTerm);
      }
      if (statusFilter && statusFilter !== "all") {
        params.set("status", statusFilter);
      }
      if (selectedUserId) {
        params.set("user_id", String(selectedUserId));
      }

      const apiResponse = await apiFetch<ResearchRunListResponseApi>(
        `/research-runs/?${params.toString()}`
      );
      const data = convertApiResearchRunList(apiResponse);
      setResearchRuns(data.items);
      setTotalCount(apiResponse.total);
    } catch {
      // silence error in prod/CI
    } finally {
      setIsLoading(false);
    }
  }, [currentPage, pageSize, searchTerm, statusFilter, selectedUserId]);

  // Load data when filters or page change
  useEffect(() => {
    loadResearchRuns();
  }, [loadResearchRuns]);

  // Reset to page 1 when filters change
  const handleSetSearchTerm = useCallback((term: string) => {
    setSearchTerm(term);
    setCurrentPage(1);
  }, []);

  const handleSetStatusFilter = useCallback((status: string) => {
    setStatusFilter(status);
    setCurrentPage(1);
  }, []);

  const handleSetSelectedUserId = useCallback((userId: number | null) => {
    setSelectedUserId(userId);
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
    selectedUserId,
    setSelectedUserId: handleSetSelectedUserId,
    isLoading,
  };

  return (
    <ProtectedRoute>
      <ResearchContext.Provider value={researchContextValue}>{children}</ResearchContext.Provider>
    </ProtectedRoute>
  );
}
