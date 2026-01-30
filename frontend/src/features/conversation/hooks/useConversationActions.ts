"use client";

import { useState, useCallback } from "react";

import { api } from "@/shared/lib/api-client-typed";
import type { ConversationDetail } from "@/types";
import { convertApiConversationDetail, isErrorResponse } from "@/shared/lib/api-adapters";

interface UseConversationActionsReturn {
  isDeleting: boolean;
  isUpdatingTitle: boolean;
  deleteConversation: (id: number) => Promise<boolean>;
  updateTitle: (id: number, newTitle: string) => Promise<ConversationDetail | null>;
}

export function useConversationActions(): UseConversationActionsReturn {
  const [isDeleting, setIsDeleting] = useState(false);
  const [isUpdatingTitle, setIsUpdatingTitle] = useState(false);

  const deleteConversation = useCallback(async (id: number): Promise<boolean> => {
    setIsDeleting(true);
    try {
      const { error } = await api.DELETE("/api/conversations/{conversation_id}", {
        params: { path: { conversation_id: id } },
      });
      if (error) throw new Error("Failed to delete conversation");
      return true;
    } catch (error) {
      // eslint-disable-next-line no-console
      console.error("Failed to delete conversation:", error);
      return false;
    } finally {
      setIsDeleting(false);
    }
  }, []);

  const updateTitle = useCallback(
    async (id: number, newTitle: string): Promise<ConversationDetail | null> => {
      const trimmedTitle = newTitle.trim();
      if (!trimmedTitle) return null;

      setIsUpdatingTitle(true);
      try {
        const { data, error } = await api.PATCH("/api/conversations/{conversation_id}", {
          params: { path: { conversation_id: id } },
          body: { title: trimmedTitle },
        });

        if (error || isErrorResponse(data)) throw new Error("Update failed");
        return convertApiConversationDetail(data.conversation);
      } catch (error) {
        // eslint-disable-next-line no-console
        console.error("Failed to update title:", error);
        return null;
      } finally {
        setIsUpdatingTitle(false);
      }
    },
    []
  );

  return {
    isDeleting,
    isUpdatingTitle,
    deleteConversation,
    updateTitle,
  };
}
