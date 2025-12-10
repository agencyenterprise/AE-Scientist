"use client";

import { DashboardContext, SortDir, SortKey } from "@/features/dashboard/contexts/DashboardContext";
import type {
  ConversationStatusFilter,
  RunStatusFilter,
} from "@/features/conversation/types/conversation-filter.types";

import { ProtectedRoute } from "@/shared/components/ProtectedRoute";
import type { Conversation } from "@/shared/lib/api-adapters";
import { convertApiConversationList } from "@/shared/lib/api-adapters";
import { apiFetch } from "@/shared/lib/api-client";
import type { ConversationListResponse } from "@/types";
import { usePathname, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

interface ConversationsLayoutProps {
  children: React.ReactNode;
}

export default function ConversationsLayout({ children }: ConversationsLayoutProps) {
  const router = useRouter();
  const pathname = usePathname();

  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [sortKey, setSortKey] = useState<SortKey>("updated");
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  const [conversationStatusFilter, setConversationStatusFilter] =
    useState<ConversationStatusFilter>("all");
  const [runStatusFilter, setRunStatusFilter] = useState<RunStatusFilter>("all");

  const selectedConversationId = pathname.startsWith("/conversations/")
    ? (() => {
        const idString = pathname.split("/")[2];
        return idString ? parseInt(idString, 10) || undefined : undefined;
      })()
    : undefined;

  const loadConversations = useCallback(async (): Promise<void> => {
    try {
      setIsLoading(true);
      // Build query string with filters
      const params = new URLSearchParams();
      params.set("limit", "500");
      params.set("offset", "0");

      // Only add filter params if they're not "all"
      if (conversationStatusFilter !== "all") {
        params.set("conversation_status", conversationStatusFilter);
      }
      if (runStatusFilter !== "all") {
        params.set("run_status", runStatusFilter);
      }

      const apiResponse = await apiFetch<ConversationListResponse>(
        `/conversations?${params.toString()}`
      );
      const data = convertApiConversationList(apiResponse);
      setConversations(data);
    } catch {
      // silence error in prod/CI
    } finally {
      setIsLoading(false);
    }
  }, [conversationStatusFilter, runStatusFilter]);

  useEffect(() => {
    loadConversations();
  }, [loadConversations]);

  const handleConversationSelect = (conversation: Conversation): void => {
    if (selectedConversationId === conversation.id) {
      return;
    }
    router.push(`/conversations/${conversation.id}`);
  };

  const dashboardContextValue = {
    conversations,
    isLoading,
    selectConversation: handleConversationSelect,
    refreshConversations: loadConversations,
    sortKey,
    setSortKey,
    sortDir,
    setSortDir,
    conversationStatusFilter,
    setConversationStatusFilter,
    runStatusFilter,
    setRunStatusFilter,
  };

  return (
    <ProtectedRoute>
      <DashboardContext.Provider value={dashboardContextValue}>
        {children}
      </DashboardContext.Provider>
    </ProtectedRoute>
  );
}
