"use client";

import { createContext, useContext } from "react";
import type { Conversation } from "@/lib/api-adapters";

export type LinearFilter = "all" | "completed" | "in_progress";
export type SortKey = "updated" | "imported" | "title" | "score";
export type SortDir = "asc" | "desc";

interface DashboardContextType {
  conversations: Conversation[];
  selectConversation: (conversation: Conversation) => void;
  refreshConversations: () => Promise<void>;
  openImportModal: () => void;
  linearFilter: LinearFilter;
  setLinearFilter: (filter: LinearFilter) => void;
  isSidebarCollapsed: boolean;
  sortKey: SortKey;
  setSortKey: (key: SortKey) => void;
  sortDir: SortDir;
  setSortDir: (dir: SortDir) => void;
}

export const DashboardContext = createContext<DashboardContextType | null>(null);

export function useDashboard() {
  const context = useContext(DashboardContext);
  if (!context) {
    throw new Error("useDashboard must be used within DashboardLayout");
  }
  return context;
}
