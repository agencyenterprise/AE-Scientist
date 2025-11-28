"use client";

import { useDashboard } from "@/features/dashboard/contexts/DashboardContext";
import { useConversationsFilter } from "@/features/conversation/hooks/useConversationsFilter";
import { ConversationsBoardHeader } from "@/features/conversation/components/ConversationsBoardHeader";
import { ConversationsBoardTable } from "@/features/conversation/components/ConversationsBoardTable";

export default function ConversationsPage() {
  const { conversations } = useDashboard();
  const { searchTerm, setSearchTerm, filteredConversations } =
    useConversationsFilter(conversations);

  return (
    <div className="flex flex-col gap-6 p-6">
      <ConversationsBoardHeader
        searchTerm={searchTerm}
        onSearchChange={setSearchTerm}
        totalCount={conversations.length}
        filteredCount={filteredConversations.length}
      />

      <ConversationsBoardTable conversations={filteredConversations} />
    </div>
  );
}
