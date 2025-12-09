"use client";

import { useMemo, useState, useCallback } from "react";
import type { Conversation } from "@/shared/lib/api-adapters";
import type {
  StatusFilterOption,
  UseConversationsFilterReturn,
} from "../types/ideation-queue.types";
import { deriveIdeaStatus } from "../utils/ideation-queue-utils";

/**
 * Hook for filtering conversations by search term and status
 * Extended to support status filtering for the Ideation Queue feature
 */
export function useConversationsFilter(
  conversations: Conversation[]
): UseConversationsFilterReturn {
  const [searchTerm, setSearchTerm] = useState("");
  const [statusFilter, setStatusFilter] = useState<StatusFilterOption>("all");

  const handleSetSearchTerm = useCallback((term: string) => {
    setSearchTerm(term);
  }, []);

  const handleSetStatusFilter = useCallback((filter: StatusFilterOption) => {
    setStatusFilter(filter);
  }, []);

  const filteredConversations = useMemo(() => {
    let filtered = conversations;

    // Apply status filter
    if (statusFilter !== "all") {
      filtered = filtered.filter(conversation => {
        const status = deriveIdeaStatus(conversation);
        return status === statusFilter;
      });
    }

    // Apply search filter
    if (searchTerm.trim()) {
      const lowerSearch = searchTerm.toLowerCase();
      filtered = filtered.filter(conversation => {
        const title = conversation.title?.toLowerCase() || "";
        const ideaTitle = conversation.ideaTitle?.toLowerCase() || "";
        const ideaAbstract = conversation.ideaAbstract?.toLowerCase() || "";
        const userName = conversation.userName?.toLowerCase() || "";
        const userEmail = conversation.userEmail?.toLowerCase() || "";

        return (
          title.includes(lowerSearch) ||
          ideaTitle.includes(lowerSearch) ||
          ideaAbstract.includes(lowerSearch) ||
          userName.includes(lowerSearch) ||
          userEmail.includes(lowerSearch)
        );
      });
    }

    return filtered;
  }, [conversations, searchTerm, statusFilter]);

  return {
    searchTerm,
    setSearchTerm: handleSetSearchTerm,
    statusFilter,
    setStatusFilter: handleSetStatusFilter,
    filteredConversations,
  };
}
