"use client";

import { createContext, useContext } from "react";
import type { ResearchRun } from "@/shared/lib/api-adapters";

export type SortKey = "updated" | "created" | "title" | "status";
export type SortDir = "asc" | "desc";

export const DEFAULT_PAGE_SIZE = 20;
export const PAGE_SIZE_OPTIONS = [10, 20, 50, 100] as const;

interface ResearchContextType {
  researchRuns: ResearchRun[];
  refreshResearchRuns: () => Promise<void>;
  sortKey: SortKey;
  setSortKey: (key: SortKey) => void;
  sortDir: SortDir;
  setSortDir: (dir: SortDir) => void;
  // Pagination
  currentPage: number;
  setCurrentPage: (page: number) => void;
  totalCount: number;
  pageSize: number;
  setPageSize: (size: number) => void;
  // Filters
  searchTerm: string;
  setSearchTerm: (term: string) => void;
  statusFilter: string;
  setStatusFilter: (status: string) => void;
  selectedUserId: number | null;
  setSelectedUserId: (userId: number | null) => void;
  isLoading: boolean;
}

export const ResearchContext = createContext<ResearchContextType | null>(null);

export function useResearch() {
  const context = useContext(ResearchContext);
  if (!context) {
    throw new Error("useResearch must be used within ResearchLayout");
  }
  return context;
}
