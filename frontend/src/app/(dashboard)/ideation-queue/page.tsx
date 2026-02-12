"use client";

import { useDashboard } from "@/features/dashboard/contexts/DashboardContext";
import { useConversationsFilter } from "@/features/conversation/hooks/useConversationsFilter";
import { IdeationQueueHeader } from "@/features/conversation/components/IdeationQueueHeader";
import { IdeationQueueList } from "@/features/conversation/components/IdeationQueueList";
import { IdeationQueueSkeleton } from "@/features/conversation/components/IdeationQueueSkeleton";
import { PageCard } from "@/shared/components/PageCard";

export default function ConversationsPage() {
  const {
    conversations,
    isLoading,
    conversationStatusFilter,
    setConversationStatusFilter,
    runStatusFilter,
    setRunStatusFilter,
  } = useDashboard();
  const { searchTerm, setSearchTerm, filteredConversations } =
    useConversationsFilter(conversations);

  const hasActiveSearch = searchTerm.trim() !== "";

  return (
    <PageCard>
      <div className="flex flex-col gap-4 p-4 sm:gap-6 sm:p-6">
        <IdeationQueueHeader
          searchTerm={searchTerm}
          onSearchChange={setSearchTerm}
          totalCount={conversations.length}
          filteredCount={filteredConversations.length}
          conversationStatusFilter={conversationStatusFilter}
          onConversationStatusChange={setConversationStatusFilter}
          runStatusFilter={runStatusFilter}
          onRunStatusChange={setRunStatusFilter}
        />

        {isLoading ? (
          <IdeationQueueSkeleton />
        ) : (
          <IdeationQueueList
            conversations={filteredConversations}
            emptyMessage={hasActiveSearch ? "No ideas match your search" : undefined}
          />
        )}
      </div>
    </PageCard>
  );
}
