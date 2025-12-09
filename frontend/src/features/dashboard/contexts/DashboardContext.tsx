"use client";

import { createContext, useContext } from "react";
import type { Conversation } from "@/shared/lib/api-adapters";

export type SortKey = "updated" | "imported" | "title" | "score";
export type SortDir = "asc" | "desc";

interface DashboardContextType {
  conversations: Conversation[];
  isLoading: boolean;
  selectConversation: (conversation: Conversation) => void;
  refreshConversations: () => Promise<void>;
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
