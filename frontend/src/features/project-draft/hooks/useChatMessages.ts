import { useState, useEffect } from "react";

import { config } from "@/shared/lib/config";
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
        const response = await fetch(`${config.apiUrl}/conversations/${conversationId}/idea/chat`, {
          method: "GET",
          credentials: "include",
        });

        if (response.ok) {
          const result = await response.json();
          if (isErrorResponse(result)) {
            // eslint-disable-next-line no-console
            console.warn("Failed to load chat history:", result.error);
            setMessages([]); // Start with empty if there's an issue
          } else {
            setMessages(result.chat_messages || []);
          }
        } else {
          // If conversation/project draft doesn't exist yet, start with empty chat
          setMessages([]);
        }
      } catch (err) {
        // eslint-disable-next-line no-console
        console.warn("Failed to load chat history:", err);
        setMessages([]); // Start with empty if there's an issue
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
