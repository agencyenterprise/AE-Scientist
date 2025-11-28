import { useState, useEffect } from "react";

import { apiFetch, ApiError } from "@/shared/lib/api-client";
import { isErrorResponse } from "@/shared/lib/api-adapters";
import type { ChatMessage } from "@/types";

interface UseChatMessagesOptions {
  conversationId: number;
}

interface UseChatMessagesReturn {
  messages: ChatMessage[];
  setMessages: React.Dispatch<React.SetStateAction<ChatMessage[]>>;
  isLoadingHistory: boolean;
}

export function useChatMessages({ conversationId }: UseChatMessagesOptions): UseChatMessagesReturn {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoadingHistory, setIsLoadingHistory] = useState(true);

  // Load chat history when conversation changes
  useEffect(() => {
    const loadChatHistory = async (): Promise<void> => {
      setIsLoadingHistory(true);

      try {
        const result = await apiFetch<{ chat_messages?: ChatMessage[] }>(
          `/conversations/${conversationId}/idea/chat`
        );
        if (isErrorResponse(result)) {
          // eslint-disable-next-line no-console
          console.warn("Failed to load chat history:", (result as { error: string }).error);
          setMessages([]); // Start with empty if there's an issue
        } else {
          setMessages(result.chat_messages || []);
        }
      } catch (err) {
        // If conversation/project draft doesn't exist yet (404), start with empty chat
        if (err instanceof ApiError && err.status === 404) {
          setMessages([]);
        } else {
          // eslint-disable-next-line no-console
          console.warn("Failed to load chat history:", err);
          setMessages([]); // Start with empty if there's an issue
        }
      } finally {
        setIsLoadingHistory(false);
      }
    };

    loadChatHistory();
  }, [conversationId]);

  return {
    messages,
    setMessages,
    isLoadingHistory,
  };
}
