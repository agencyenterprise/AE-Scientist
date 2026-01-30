import { useState, useEffect, useRef } from "react";

import { api } from "@/shared/lib/api-client-typed";
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
  const pollingIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const isPollingRef = useRef(false);

  // Load chat history when conversation changes
  useEffect(() => {
    const loadChatHistory = async (): Promise<void> => {
      setIsLoadingHistory(true);

      const { data, error } = await api.GET("/api/conversations/{conversation_id}/idea/chat", {
        params: { path: { conversation_id: conversationId } },
      });

      if (error) {
        // If conversation/project draft doesn't exist yet (404), start with empty chat
        // eslint-disable-next-line no-console
        console.warn("Failed to load chat history:", error);
        setMessages([]); // Start with empty if there's an issue
      } else if (data && "chat_messages" in data) {
        setMessages((data.chat_messages as ChatMessage[]) || []);
      } else {
        setMessages([]);
      }

      setIsLoadingHistory(false);
    };

    loadChatHistory();
  }, [conversationId]);

  // Compute whether we have an empty assistant message (used for polling status)
  const lastMessage = messages[messages.length - 1];
  const hasEmptyAssistantMessage =
    !isLoadingHistory &&
    !!lastMessage &&
    lastMessage.role === "assistant" &&
    !lastMessage.content.trim();

  // Poll for updates if last message is an empty assistant message
  // This handles the case where user refreshed during streaming
  useEffect(() => {
    // Don't poll while loading history or if no empty assistant message
    if (isLoadingHistory || !hasEmptyAssistantMessage) {
      // Clear any existing polling
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
        pollingIntervalRef.current = null;
      }
      isPollingRef.current = false;
      return;
    }

    // Start polling for updates
    isPollingRef.current = true;
    const pollForUpdates = async (): Promise<void> => {
      const { data, error } = await api.GET("/api/conversations/{conversation_id}/idea/chat", {
        params: { path: { conversation_id: conversationId } },
      });

      if (error) {
        // eslint-disable-next-line no-console
        console.debug("Polling for message updates failed:", error);
        return;
      }

      if (data && "chat_messages" in data && data.chat_messages) {
        const chatMessages = data.chat_messages as ChatMessage[];
        const updatedLastMessage = chatMessages[chatMessages.length - 1];
        // If the last message now has content, update and stop polling
        if (updatedLastMessage?.content.trim()) {
          setMessages(chatMessages);
          if (pollingIntervalRef.current) {
            clearInterval(pollingIntervalRef.current);
            pollingIntervalRef.current = null;
          }
          isPollingRef.current = false;
        }
      }
    };

    // Poll every 2 seconds
    pollingIntervalRef.current = setInterval(pollForUpdates, 2000);

    // Cleanup on unmount or when dependencies change
    return () => {
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
        pollingIntervalRef.current = null;
      }
      isPollingRef.current = false;
    };
  }, [conversationId, isLoadingHistory, hasEmptyAssistantMessage]);

  return {
    messages,
    setMessages,
    isLoadingHistory,
    // Derive polling status from whether we have an empty assistant message
    isPollingEmptyMessage: hasEmptyAssistantMessage,
  };
}
