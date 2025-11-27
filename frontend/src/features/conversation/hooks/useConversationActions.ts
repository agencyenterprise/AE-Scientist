"use client";

import { useState, useCallback } from "react";

import { config } from "@/shared/lib/config";
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
      const response = await fetch(`${config.apiUrl}/conversations/${id}`, {
        method: "DELETE",
        credentials: "include",
      });

      if (response.ok) {
        return true;
      }
      throw new Error("Failed to delete conversation");
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
        const response = await fetch(`${config.apiUrl}/conversations/${id}`, {
          method: "PATCH",
          headers: {
            "Content-Type": "application/json",
          },
          credentials: "include",
          body: JSON.stringify({ title: trimmedTitle }),
        });

        const result: ConversationUpdateResponse | ErrorResponse = await response.json();

        if (response.ok && !isErrorResponse(result)) {
          return convertApiConversationDetail(result.conversation);
        }
        const errorMsg = isErrorResponse(result) ? result.error : "Update failed";
        throw new Error(errorMsg);
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
