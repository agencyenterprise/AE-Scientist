"use client";

import { useMemo, useState, useCallback } from "react";
import type { Conversation } from "@/shared/lib/api-adapters";

interface UseConversationsFilterReturn {
  searchTerm: string;
  setSearchTerm: (term: string) => void;
  filteredConversations: Conversation[];
}

export function useConversationsFilter(
  conversations: Conversation[]
): UseConversationsFilterReturn {
  const [searchTerm, setSearchTerm] = useState("");

  const handleSetSearchTerm = useCallback((term: string) => {
    setSearchTerm(term);
  }, []);

  const filteredConversations = useMemo(() => {
    if (!searchTerm.trim()) {
      return conversations;
    }

    const lowerSearch = searchTerm.toLowerCase();
    return conversations.filter(conversation => {
      const title = conversation.title?.toLowerCase() || "";
      const ideaTitle = conversation.ideaTitle?.toLowerCase() || "";
      const userName = conversation.userName?.toLowerCase() || "";
      const userEmail = conversation.userEmail?.toLowerCase() || "";

      return (
        title.includes(lowerSearch) ||
        ideaTitle.includes(lowerSearch) ||
        userName.includes(lowerSearch) ||
        userEmail.includes(lowerSearch)
      );
    });
  }, [conversations, searchTerm]);

  return {
    searchTerm,
    setSearchTerm: handleSetSearchTerm,
    filteredConversations,
  };
}
