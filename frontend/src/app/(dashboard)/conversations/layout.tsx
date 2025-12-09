"use client";

import { DashboardContext, SortDir, SortKey } from "@/features/dashboard/contexts/DashboardContext";

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

  const selectedConversationId = pathname.startsWith("/conversations/")
    ? (() => {
        const idString = pathname.split("/")[2];
        return idString ? parseInt(idString, 10) || undefined : undefined;
      })()
    : undefined;

  const loadConversations = useCallback(async (): Promise<void> => {
    try {
      setIsLoading(true);
      const apiResponse = await apiFetch<ConversationListResponse>(
        "/conversations?limit=500&offset=0"
      );
      const data = convertApiConversationList(apiResponse);
      setConversations(data);
    } catch {
      // silence error in prod/CI
    } finally {
      setIsLoading(false);
    }
  }, []);

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
  };

  return (
    <ProtectedRoute>
      <DashboardContext.Provider value={dashboardContextValue}>
        {children}
      </DashboardContext.Provider>
    </ProtectedRoute>
  );
}
