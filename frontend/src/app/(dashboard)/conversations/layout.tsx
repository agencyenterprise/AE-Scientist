"use client";

import { DashboardContext, SortDir, SortKey } from "@/features/dashboard/contexts/DashboardContext";
import { useCallback, useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";

import { ProtectedRoute } from "@/shared/components/ProtectedRoute";
import { config } from "@/shared/lib/config";
import type { Conversation } from "@/shared/lib/api-adapters";
import { convertApiConversationList } from "@/shared/lib/api-adapters";

interface ConversationsLayoutProps {
  children: React.ReactNode;
}

export default function ConversationsLayout({ children }: ConversationsLayoutProps) {
  const router = useRouter();
  const pathname = usePathname();

  const [conversations, setConversations] = useState<Conversation[]>([]);
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
      const response = await fetch(`${config.apiUrl}/conversations?limit=500&offset=0`, {
        credentials: "include",
      });
      if (response.ok) {
        const apiResponse = await response.json();
        const data = convertApiConversationList(apiResponse);
        setConversations(data);
      }
    } catch {
      // silence error in prod/CI
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
