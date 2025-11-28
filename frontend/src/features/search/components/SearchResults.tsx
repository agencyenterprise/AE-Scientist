"use client";

import React, { useCallback, useMemo } from "react";
import type { SearchResult, SearchStats } from "@/types";
import {
  ConversationCard,
  toSearchMatchFromHit,
} from "@/features/conversation/components/ConversationCard";
import { useDashboard } from "@/features/dashboard/contexts/DashboardContext";
import type { Conversation } from "@/shared/lib/api-adapters";
import { Search } from "lucide-react";

interface SearchResultsProps {
  results: SearchResult[];
  stats: SearchStats | null;
  isLoading: boolean;
  hasMore: boolean;
  onLoadMore: () => void;
  query: string;
  error: string | null;
}

interface ConversationGroup {
  conversation_id: number;
  title: string;
  results: SearchResult[];
}

interface ConversationGroupProps {
  group: ConversationGroup;
  query: string;
}

// Removed old content-type styling config in favor of unified ConversationCard

function escapeHtml(input: string): string {
  return input
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function highlightQuery(snippet: string, query: string): string {
  if (!query.trim()) return escapeHtml(snippet);
  try {
    const escapedSnippet = escapeHtml(snippet);
    const safeQuery = query.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    const regex = new RegExp(`(${safeQuery})`, "gi");
    return escapedSnippet.replace(regex, "<mark>$1</mark>");
  } catch {
    return escapeHtml(snippet);
  }
}

function ConversationGroup({ group, query }: ConversationGroupProps): React.JSX.Element {
  // time formatting handled inside ConversationCard

  const getConversationTitle = useCallback(() => {
    // Use the conversation_title field that's now included in all search results
    return group.results[0]?.conversation_title || "Untitled Conversation";
  }, [group.results]);

  const contentTypeGroups = useMemo(() => {
    const groupMap = new Map<string, SearchResult[]>();

    // Group results by content_type
    group.results.forEach(result => {
      const contentType = result.content_type;
      if (!groupMap.has(contentType)) {
        groupMap.set(contentType, []);
      }
      const typeGroup = groupMap.get(contentType);
      if (typeGroup) {
        typeGroup.push(result);
      }
    });

    // Convert to array, sort each group's results by score desc, then order groups by their max score desc
    const groups = Array.from(groupMap.entries()).map(([content_type, results]) => {
      const sortedResults = [...results].sort((a, b) => b.score - a.score);
      const first = sortedResults.at(0);
      const maxScore = first ? first.score : -Infinity;
      return {
        content_type,
        // Limit to top 1 match per content type group
        results: first ? [first] : [],
        maxScore,
      };
    });

    groups.sort((a, b) => {
      if (a.maxScore !== b.maxScore) return b.maxScore - a.maxScore;
      return a.content_type.localeCompare(b.content_type);
    });

    return groups.map(({ content_type, results }) => ({ content_type, results }));
  }, [group.results]);

  const { conversations, selectConversation } = useDashboard();

  // Find the conversation record to power the unified card
  const conversation: Conversation | undefined = useMemo(() => {
    const convId = group.conversation_id;
    return conversations.find(c => c.id === convId);
  }, [conversations, group.conversation_id]);

  // Pick top content-type result (first in max-score order)
  const topHit: SearchResult | undefined = useMemo(() => {
    const firstGroup = contentTypeGroups[0];
    if (!firstGroup || firstGroup.results.length === 0) return undefined;
    return firstGroup.results[0];
  }, [contentTypeGroups]);

  // Precompute best per content-type (no hooks after early return)
  const projectDraftMatch = (() => {
    const pd = contentTypeGroups.find(g => g.content_type === "project_draft");
    const hit = pd?.results?.[0];
    return hit ? toSearchMatchFromHit(hit, query) : null;
  })();
  const draftChatMatch = (() => {
    const dc = contentTypeGroups.find(g => g.content_type === "draft_chat");
    const hit = dc?.results?.[0];
    return hit ? toSearchMatchFromHit(hit, query) : null;
  })();
  const importedChatMatch = (() => {
    const conv = contentTypeGroups.find(g => g.content_type === "imported_chat");
    const hit = conv?.results?.[0];
    return hit ? toSearchMatchFromHit(hit, query) : null;
  })();

  if (!conversation || !topHit) {
    // Fallback to previous minimal block if conversation metadata not loaded yet
    return (
      <div className="border border-border rounded-lg bg-card shadow-sm p-3">
        <div
          className="font-semibold text-foreground text-sm mb-2"
          dangerouslySetInnerHTML={{ __html: getConversationTitle() }}
        />
        <p
          className="text-sm text-muted-foreground"
          dangerouslySetInnerHTML={{
            __html: highlightQuery(group.results[0]?.content_snippet || "", query),
          }}
        />
      </div>
    );
  }

  const match = toSearchMatchFromHit(topHit, query);

  return (
    <ConversationCard
      conversation={conversation}
      onSelect={c => selectConversation(c)}
      searchMatch={match}
      draftChatMatch={draftChatMatch}
      projectDraftMatch={projectDraftMatch}
      importedChatMatch={importedChatMatch}
    />
  );
}

export function SearchResults({
  results,
  stats,
  isLoading,
  hasMore,
  onLoadMore,
  query,
  error,
}: SearchResultsProps): React.JSX.Element {
  // Group results by conversation_id
  const conversationGroups = useMemo(() => {
    if (!results.length) return [];

    const groupMap = new Map<number, SearchResult[]>();

    // Group results by conversation_id
    results.forEach(result => {
      const conversationId = result.conversation_id;
      if (!groupMap.has(conversationId)) {
        groupMap.set(conversationId, []);
      }
      const group = groupMap.get(conversationId);
      if (group) {
        group.push(result);
      }
    });

    // Convert to array of ConversationGroup objects
    return Array.from(groupMap.entries()).map(([conversation_id, results]) => ({
      conversation_id,
      title: "", // Will be determined in ConversationGroup component
      results,
    }));
  }, [results]);

  // Navigation handled by ConversationCard via Dashboard context selection

  const handleLoadMore = useCallback(() => {
    if (!isLoading && hasMore) {
      onLoadMore();
    }
  }, [isLoading, hasMore, onLoadMore]);

  // Preserve backend ordering of conversation groups (backend already applies sorting)
  const sortedGroups = useMemo(() => {
    return conversationGroups;
  }, [conversationGroups]);

  // Error State
  if (error) {
    return (
      <div className="text-center py-8">
        <div className="text-destructive mb-2">Search Error</div>
        <p className="text-muted-foreground text-sm">{error}</p>
      </div>
    );
  }

  // Welcome State (when no query has been entered)
  if (!isLoading && results.length === 0 && !query) {
    return (
      <div className="flex flex-col items-center justify-center text-center h-full min-h-96">
        {/* Search Icon */}
        <div className="bg-primary/20 p-4 rounded-full mb-6">
          <Search className="h-12 w-12 text-primary" />
        </div>

        {/* Welcome Message */}
        <h2 className="text-2xl font-bold text-foreground mb-4">Search Your Knowledge Base</h2>
        <p className="text-muted-foreground text-lg max-w-xl">
          Find information across all your conversations, imported chats, and project drafts
        </p>
      </div>
    );
  }

  // Empty State (when query was entered but no results found)
  if (!isLoading && results.length === 0 && query) {
    return (
      <div className="text-center py-8">
        <Search className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
        <h3 className="text-lg font-medium text-foreground mb-2">No results found</h3>
        <p className="text-muted-foreground text-sm">
          Try adjusting your search query or check your spelling.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Grouped Search Results */}
      <div className="space-y-4">
        {sortedGroups.map(group => (
          <ConversationGroup key={group.conversation_id} group={group} query={query} />
        ))}
      </div>

      {/* Loading State */}
      {isLoading && (
        <div className="text-center py-8">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto mb-4"></div>
          <p className="text-muted-foreground text-sm">Searching...</p>
        </div>
      )}

      {/* Load More Button */}
      {hasMore && !isLoading && results.length > 0 && (
        <div className="text-center py-4">
          <button
            onClick={handleLoadMore}
            className="px-6 py-2 bg-primary text-primary-foreground rounded-lg hover:opacity-90 transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-primary"
          >
            Load More Results
          </button>
        </div>
      )}

      {/* End of Results with Stats */}
      {!hasMore && results.length > 0 && !isLoading && stats && (
        <div className="text-center py-4 text-muted-foreground text-sm">
          {sortedGroups.length} conversation
          {sortedGroups.length !== 1 ? "s" : ""} • {stats.execution_time_ms.toFixed(0)}ms
        </div>
      )}
    </div>
  );
}
