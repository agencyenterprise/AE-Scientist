import { useState, useEffect, useRef } from "react";

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
  isPollingEmptyMessage: boolean;
}

export function useChatMessages({ conversationId }: UseChatMessagesOptions): UseChatMessagesReturn {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoadingHistory, setIsLoadingHistory] = useState(true);
  const [isPollingEmptyMessage, setIsPollingEmptyMessage] = useState(false);
  const pollingIntervalRef = useRef<NodeJS.Timeout | null>(null);

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

  // Poll for updates if last message is an empty assistant message
  // This handles the case where user refreshed during streaming
  useEffect(() => {
    // Don't poll while loading history
    if (isLoadingHistory) {
      return;
    }

    const lastMessage = messages[messages.length - 1];
    const hasEmptyAssistantMessage =
      lastMessage && lastMessage.role === "assistant" && !lastMessage.content.trim();

    if (hasEmptyAssistantMessage) {
      // Start polling for updates
      setIsPollingEmptyMessage(true);
      const pollForUpdates = async (): Promise<void> => {
        try {
          const result = await apiFetch<{ chat_messages?: ChatMessage[] }>(
            `/conversations/${conversationId}/idea/chat`
          );
          if (!isErrorResponse(result) && result.chat_messages) {
            const updatedLastMessage = result.chat_messages[result.chat_messages.length - 1];
            // If the last message now has content, update and stop polling
            if (updatedLastMessage?.content.trim()) {
              setMessages(result.chat_messages);
              setIsPollingEmptyMessage(false);
              if (pollingIntervalRef.current) {
                clearInterval(pollingIntervalRef.current);
                pollingIntervalRef.current = null;
              }
            }
          }
        } catch (err) {
          // eslint-disable-next-line no-console
          console.debug("Polling for message updates failed:", err);
        }
      };

      // Poll every 2 seconds
      pollingIntervalRef.current = setInterval(pollForUpdates, 2000);
    } else {
      // No empty assistant message, make sure polling is stopped
      setIsPollingEmptyMessage(false);
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
        pollingIntervalRef.current = null;
      }
    }

    // Cleanup on unmount or when dependencies change
    return () => {
      setIsPollingEmptyMessage(false);
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
        pollingIntervalRef.current = null;
      }
    };
  }, [conversationId, messages, isLoadingHistory]);

  return {
    messages,
    setMessages,
    isLoadingHistory,
    isPollingEmptyMessage,
  };
}
