"use client";

import { useMemo } from "react";
import { useDashboard } from "@/app/(dashboard)/DashboardContext";

import type { Conversation } from "@/lib/api-adapters";
import { ConversationCard } from "@/components/ConversationCard";

interface ConversationsGridProps {
  conversations: Conversation[];
  onSelect: (conversation: Conversation) => void;
}

// LinearFilter now lives in DashboardContext

export function ConversationsGrid({ conversations, onSelect }: ConversationsGridProps) {
  const { sortKey, sortDir } = useDashboard();

  const filtered = useMemo(() => {
    // Sort
    const sorted = [...conversations].sort((a, b) => {
      if (sortKey === "title") {
        return (a.title || "").localeCompare(b.title || "", undefined, { sensitivity: "base" });
      }
      if (sortKey === "imported") {
        return new Date(a.importDate).getTime() - new Date(b.importDate).getTime();
      }
      // "score" not applicable to dashboard list; fall back to updated
      // default updated
      return new Date(a.updatedAt).getTime() - new Date(b.updatedAt).getTime();
    });
    if (sortDir === "desc") sorted.reverse();
    return sorted;
  }, [conversations, sortKey, sortDir]);

  return (
    <div className="h-full flex flex-col">
      {/* Toolbar removed: list view only */}

      {/* Grid */}
      <div className="flex-1 overflow-auto p-4 sm:p-6 bg-gray-50">
        {filtered.length === 0 ? (
          <div className="h-full flex items-center justify-center">
            <div className="text-center max-w-md">
              <h2 className="text-lg font-medium text-gray-900 mb-2">No conversations found</h2>
              <p className="text-gray-600 text-sm">Try changing filters or search terms.</p>
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            {filtered.map(c => (
              <ConversationCard key={c.id} conversation={c} onSelect={onSelect} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
