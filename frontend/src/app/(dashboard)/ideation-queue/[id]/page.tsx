"use client";

import { ConversationView } from "@/features/conversation/components/ConversationView";
import { useDashboard } from "@/features/dashboard/contexts/DashboardContext";
import { api } from "@/shared/lib/api-client-typed";
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
        const [conversationResult, costsResult] = await Promise.all([
          api.GET("/api/conversations/{conversation_id}", {
            params: { path: { conversation_id: id } },
          }),
          api.GET("/api/conversations/{conversation_id}/costs", {
            params: { path: { conversation_id: id } },
          }),
        ]);

        if (conversationResult.error) throw new Error("Failed to load conversation");
        if (costsResult.error) throw new Error("Failed to load costs");

        setSelectedConversation(conversationResult.data as ConversationDetail);
        setCostDetails(costsResult.data as ConversationCostResponse);
        return conversationResult.data as ConversationDetail;
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
      const { data: costs, error } = await api.GET("/api/conversations/{conversation_id}/costs", {
        params: { path: { conversation_id: conversationId } },
      });
      if (error) throw new Error("Failed to refresh cost details");
      setCostDetails(costs as ConversationCostResponse);
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

  return (
    <div className="p-3 sm:p-6">
      <ConversationView
        conversation={selectedConversation}
        isLoading={isLoading && !selectedConversation}
        onConversationDeleted={handleConversationDeleted}
        onTitleUpdated={handleTitleUpdated}
        onSummaryGenerated={handleSummaryGenerated}
        expandImportedChat={expandImportedChat}
        costDetails={costDetails}
        onRefreshCostDetails={refreshCostDetails}
      />
    </div>
  );
}
