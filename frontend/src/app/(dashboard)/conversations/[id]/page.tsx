"use client";

import { ConversationView } from "@/features/conversation/components/ConversationView";
import { useDashboard } from "@/features/dashboard/contexts/DashboardContext";
import { apiFetch } from "@/shared/lib/api-client";
import type { ConversationDetail, ConversationCostResponse } from "@/types";
import { useSearchParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

interface ConversationPageProps {
  params: Promise<{
    id: string;
  }>;
}

export default function ConversationPage({ params }: ConversationPageProps) {
  const { refreshConversations } = useDashboard();
  const searchParams = useSearchParams();
  const [conversationId, setConversationId] = useState<number | null>(null);
  const [selectedConversation, setSelectedConversation] = useState<
    ConversationDetail | undefined
  >();
  const [isLoading, setIsLoading] = useState(false);
  const [costDetails, setCostDetails] = useState<ConversationCostResponse | null>(null);

  // Check URL parameters for initial panel state
  const expandImportedChat = searchParams.get("expand") === "imported";

  const loadConversationDetail = useCallback(
    async (id: number): Promise<ConversationDetail | null> => {
      setIsLoading(true);

      try {
        const [conversationDetail, costs] = await Promise.all([
          apiFetch<ConversationDetail>(`/conversations/${id}`),
          apiFetch<ConversationCostResponse>(`/conversations/${id}/costs`),
        ]);

        setSelectedConversation(conversationDetail);
        setCostDetails(costs);
        return conversationDetail;
      } catch (error) {
        // eslint-disable-next-line no-console
        console.error("Failed to load conversation detail:", error);
      } finally {
        setIsLoading(false);
      }

      return null;
    },
    []
  );

  // Resolve params on mount
  useEffect(() => {
    const resolveParams = async () => {
      const resolvedParams = await params;
      const id = parseInt(resolvedParams.id, 10);
      setConversationId(id);
    };
    resolveParams();
  }, [params]);

  // Load selected conversation when conversationId is available
  useEffect(() => {
    if (conversationId !== null && !isNaN(conversationId)) {
      loadConversationDetail(conversationId);
    }
  }, [conversationId, loadConversationDetail]);

  const refreshCostDetails = useCallback(async () => {
    if (conversationId === null) return;
    try {
      const costs = await apiFetch<ConversationCostResponse>(
        `/conversations/${conversationId}/costs`
      );
      setCostDetails(costs);
    } catch (error) {
      // eslint-disable-next-line no-console
      console.error("Failed to refresh cost details:", error);
    }
  }, [conversationId]);

  const handleConversationDeleted = async (): Promise<void> => {
    // Navigate back to home - this will be handled by the layout's conversation select
    window.location.href = "/";
  };

  const handleTitleUpdated = async (updatedConversation: ConversationDetail): Promise<void> => {
    // Update the selected conversation with the new title
    setSelectedConversation(updatedConversation);

    // Refresh the conversation list to show the updated title
    await refreshConversations();
  };

  const handleSummaryGenerated = (summary: string): void => {
    // Update the selected conversation with the new summary
    if (selectedConversation) {
      const updated = {
        ...selectedConversation,
        summary,
      };
      setSelectedConversation(updated);
    }
  };

  const handleConversationLocked = async (): Promise<void> => {
    // Refresh conversation data to get the updated locked state
    if (conversationId !== null && !isNaN(conversationId)) {
      loadConversationDetail(conversationId);
      // Also refresh the conversation list to update the sidebar
      await refreshConversations();
    }
  };

  return (
    <div className="p-6">
      <ConversationView
        conversation={selectedConversation}
        isLoading={isLoading && !selectedConversation}
        onConversationDeleted={handleConversationDeleted}
        onTitleUpdated={handleTitleUpdated}
        onSummaryGenerated={handleSummaryGenerated}
        onConversationLocked={handleConversationLocked}
        expandImportedChat={expandImportedChat}
        costDetails={costDetails}
        onRefreshCostDetails={refreshCostDetails}
      />
    </div>
  );
}
