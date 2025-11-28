"use client";

import { useState, useCallback } from "react";

import { apiFetch } from "@/shared/lib/api-client";
import type { ConversationDetail, ConversationUpdateResponse, ErrorResponse } from "@/types";
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
      await apiFetch<void>(`/conversations/${id}`, {
        method: "DELETE",
        skipJson: true,
      });
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
        const result = await apiFetch<ConversationUpdateResponse | ErrorResponse>(
          `/conversations/${id}`,
          {
            method: "PATCH",
            body: { title: trimmedTitle },
          }
        );

        if (!isErrorResponse(result)) {
          return convertApiConversationDetail(result.conversation);
        }
        throw new Error(result.error ?? "Update failed");
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
