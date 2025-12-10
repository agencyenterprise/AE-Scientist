"use client";

import { createContext, useContext } from "react";
import type { Conversation } from "@/shared/lib/api-adapters";
import type {
  ConversationStatusFilter,
  RunStatusFilter,
} from "@/features/conversation/types/conversation-filter.types";

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
  conversationStatusFilter: ConversationStatusFilter;
  setConversationStatusFilter: (filter: ConversationStatusFilter) => void;
  runStatusFilter: RunStatusFilter;
  setRunStatusFilter: (filter: RunStatusFilter) => void;
}

export const DashboardContext = createContext<DashboardContextType | null>(null);

export function useDashboard() {
  const context = useContext(DashboardContext);
  if (!context) {
    throw new Error("useDashboard must be used within DashboardLayout");
  }
  return context;
}
