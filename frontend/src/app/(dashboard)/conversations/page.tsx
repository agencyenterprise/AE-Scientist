"use client";

import { useState, useRef, useEffect } from "react";
import { useDashboard } from "@/features/dashboard/contexts/DashboardContext";
import { useConversationsFilter } from "@/features/conversation/hooks/useConversationsFilter";
import { IdeationQueueHeader } from "@/features/conversation/components/IdeationQueueHeader";
import { IdeationQueueList } from "@/features/conversation/components/IdeationQueueList";
import { IdeationQueueSkeleton } from "@/features/conversation/components/IdeationQueueSkeleton";
import { InlineIdeaView } from "@/features/conversation/components/InlineIdeaView";
import { useSelectedIdeaData } from "@/features/conversation/hooks/useSelectedIdeaData";
import { PageCard } from "@/shared/components/PageCard";

export default function ConversationsPage() {
  const { conversations, isLoading } = useDashboard();
  const { searchTerm, setSearchTerm, filteredConversations } =
    useConversationsFilter(conversations);
  const [selectedConversationId, setSelectedConversationId] = useState<number | null>(null);
  const inlineViewRef = useRef<HTMLDivElement>(null);

  // Monitor loading state of selected idea
  const { isLoading: ideaIsLoading } = useSelectedIdeaData(selectedConversationId);

  const hasActiveSearch = searchTerm.trim() !== "";

  // Scroll to inline view AFTER content has loaded
  useEffect(() => {
    // Only scroll when:
    // 1. A conversation is selected
    // 2. Content has finished loading
    // 3. Ref is available
    if (selectedConversationId !== null && !ideaIsLoading && inlineViewRef.current) {
      // Small delay to ensure DOM has painted
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          inlineViewRef.current?.scrollIntoView({
            behavior: "smooth",
            block: "start",
            inline: "nearest",
          });
        });
      });
    }
  }, [selectedConversationId, ideaIsLoading]);

  return (
    <>
      {/* Main Card */}
      <PageCard>
        <div className="flex flex-col gap-6 p-6">
          <IdeationQueueHeader
            searchTerm={searchTerm}
            onSearchChange={setSearchTerm}
            totalCount={conversations.length}
            filteredCount={filteredConversations.length}
          />

          {isLoading ? (
            <IdeationQueueSkeleton />
          ) : (
            <IdeationQueueList
              conversations={filteredConversations}
              emptyMessage={hasActiveSearch ? "No ideas match your search" : undefined}
              selectedId={selectedConversationId}
              onSelect={setSelectedConversationId}
            />
          )}
        </div>
      </PageCard>

      {/* Inline Idea View Card */}
      <PageCard>
        <div ref={inlineViewRef} className="p-6">
          <InlineIdeaView conversationId={selectedConversationId} />
        </div>
      </PageCard>
    </>
  );
}
