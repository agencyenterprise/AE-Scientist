import { useState, useRef, useEffect, useCallback } from "react";

import { config } from "@/shared/lib/config";
import { isErrorResponse } from "@/shared/lib/api-adapters";
import type {
  ChatMessage,
  ChatRequest,
  ChatStreamEvent,
  FileAttachment,
  FileMetadata,
  Idea,
} from "@/types";
import type { User } from "@/types/auth";

import { STATUS_MESSAGES, isChatStatus } from "../utils/chatTypes";

interface UseChatStreamingOptions {
  conversationId: number;
  user: User;
  currentModel: string;
  currentProvider: string;
  messages: ChatMessage[];
  setMessages: React.Dispatch<React.SetStateAction<ChatMessage[]>>;
  onProjectDraftUpdate?: (updatedDraft: Idea) => void;
  onConversationLocked?: () => void;
  consumePendingFiles: () => FileMetadata[];
  restorePendingFiles: (files: FileMetadata[]) => void;
  inputRef?: React.RefObject<HTMLTextAreaElement | null>;
  onStreamEnd?: () => void;
}

interface UseChatStreamingReturn {
  isStreaming: boolean;
  streamingContent: string;
  statusMessage: string;
  error: string | null;
  sendMessage: (inputMessage: string) => Promise<void>;
  clearError: () => void;
}

export function useChatStreaming({
  conversationId,
  user,
  currentModel,
  currentProvider,
  messages,
  setMessages,
  onProjectDraftUpdate,
  onConversationLocked,
  consumePendingFiles,
  restorePendingFiles,
  inputRef,
  onStreamEnd,
}: UseChatStreamingOptions): UseChatStreamingReturn {
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamingContent, setStreamingContent] = useState("");
  const [statusMessage, setStatusMessage] = useState("");
  const [error, setError] = useState<string | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);

  // Cleanup EventSource on unmount
  useEffect(() => {
    const currentEventSource = eventSourceRef.current;
    return () => {
      if (currentEventSource) {
        currentEventSource.close();
      }
    };
  }, []);

  const clearError = useCallback(() => {
    setError(null);
  }, []);

  const sendMessage = useCallback(
    async (inputMessage: string): Promise<void> => {
      if (!inputMessage.trim() || isStreaming) return;

      // Use the current model and provider (set by ModelSelector)
      if (!currentModel || !currentProvider) {
        setError("LLM model and provider are required. Please wait for model to load.");
        return;
      }

      const userMessage = inputMessage.trim();
      // Consume pending files
      const currentFiles = consumePendingFiles();
      const attachmentIds: number[] = currentFiles.map(file => file.id);

      setError(null);
      setIsStreaming(true);
      setStreamingContent("");
      setStatusMessage("Sending message...");

      // Reset textarea height when sending message
      if (inputRef?.current) {
        inputRef.current.style.height = "auto";
      }

      // Convert pending files to attachments format
      const messageAttachments: FileAttachment[] = currentFiles.map(file => ({
        id: file.id,
        filename: file.filename,
        file_size: file.file_size,
        file_type: file.file_type,
        s3_key: file.s3_key,
        created_at: new Date().toISOString(),
      }));

      // Optimistically add user message
      const optimisticUserMessage: ChatMessage = {
        role: "user",
        content: userMessage,
        sequence_number: messages.length + 1,
        created_at: new Date().toISOString(),
        sent_by_user_id: user.id,
        sent_by_user_name: user.name,
        sent_by_user_email: user.email,
        attachments: messageAttachments,
      };
      setMessages(prev => [...prev, optimisticUserMessage]);

      // Setup timeout for streaming connection
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 300000); // 5 minute timeout

      try {
        // Use fetch for streaming POST request with timeout
        const response = await fetch(
          `${config.apiUrl}/conversations/${conversationId}/idea/chat/stream`,
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              Accept: "text/event-stream",
            },
            credentials: "include",
            body: JSON.stringify({
              message: userMessage,
              llm_model: currentModel,
              llm_provider: currentProvider,
              attachment_ids: attachmentIds,
            } as ChatRequest),
            signal: controller.signal,
          }
        );

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }

        if (!response.body) {
          throw new Error("No response body");
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();

        let accumulatedContent = "";
        let projectUpdated = false;
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() || ""; // Keep incomplete line in buffer

          for (const line of lines) {
            if (!line.trim()) continue;

            try {
              const eventData = JSON.parse(line) as ChatStreamEvent;
              let shouldExitLineLoop = false;
              switch (eventData.type) {
                case "status": {
                  const statusValue = eventData.data;
                  if (isChatStatus(statusValue)) {
                    const displayMessage = STATUS_MESSAGES[statusValue];
                    setStatusMessage(displayMessage);
                  } else {
                    // eslint-disable-next-line no-console
                    console.warn(`Unknown status value received: ${statusValue}`);
                    setStatusMessage("");
                  }
                  break;
                }
                case "content": {
                  const content = eventData.data;
                  accumulatedContent += content;
                  setStreamingContent(accumulatedContent);
                  break;
                }
                case "idea_updated": {
                  projectUpdated = true;
                  setStatusMessage("Idea updated!");
                  break;
                }
                case "conversation_locked": {
                  setStatusMessage("Project created successfully!");
                  if (onConversationLocked) {
                    onConversationLocked();
                  }
                  break;
                }
                case "error": {
                  throw new Error(eventData.data);
                }
                case "done": {
                  shouldExitLineLoop = true;
                  break;
                }
              }
              if (shouldExitLineLoop) {
                break;
              }
            } catch (parseError) {
              // eslint-disable-next-line no-console
              console.warn("Failed to parse JSON line:", line, "Error:", parseError);
            }
          }
        }

        const trimmedContent = accumulatedContent.trim();
        if (trimmedContent) {
          setMessages(prev => {
            if (prev.some(msg => msg.content === trimmedContent && msg.role === "assistant")) {
              return prev;
            }
            const assistantMessage: ChatMessage = {
              role: "assistant",
              content: trimmedContent,
              sequence_number: prev.length + 1,
              created_at: new Date().toISOString(),
              sent_by_user_id: user.id,
              sent_by_user_name: user.name,
              sent_by_user_email: user.email,
              attachments: [],
            };
            return [...prev, assistantMessage];
          });
        }

        // Trigger idea update if needed
        if (projectUpdated && onProjectDraftUpdate) {
          // Fetch the latest idea data
          try {
            const ideaResponse = await fetch(
              `${config.apiUrl}/conversations/${conversationId}/idea`,
              {
                credentials: "include",
              }
            );
            if (ideaResponse.ok) {
              const result = await ideaResponse.json();
              if (!isErrorResponse(result) && result.idea) {
                onProjectDraftUpdate(result.idea);
              }
            }
          } catch (err) {
            // eslint-disable-next-line no-console
            console.error("Failed to fetch updated idea:", err);
          }
        }
      } catch (err) {
        const errorMessage = err instanceof Error ? err.message : "Failed to send message";
        setError(errorMessage);
        // eslint-disable-next-line no-console
        console.error("Streaming error:", err);

        // Remove optimistic message on error and restore files
        setMessages(prev => prev.slice(0, -1));
        restorePendingFiles(currentFiles);
      } finally {
        // Always clear timeout
        clearTimeout(timeoutId);
        setIsStreaming(false);
        setStreamingContent("");
        setStatusMessage("");

        if (onStreamEnd) {
          onStreamEnd();
        }

        // Focus input field when response is complete and reset height
        // Use setTimeout to ensure state updates are applied first
        setTimeout(() => {
          if (inputRef?.current) {
            inputRef.current.focus();
            inputRef.current.style.height = "auto";
          }
        }, 100);
      }
    },
    [
      isStreaming,
      currentModel,
      currentProvider,
      consumePendingFiles,
      inputRef,
      messages.length,
      user,
      setMessages,
      conversationId,
      onConversationLocked,
      onProjectDraftUpdate,
      restorePendingFiles,
      onStreamEnd,
    ]
  );

  return {
    isStreaming,
    streamingContent,
    statusMessage,
    error,
    sendMessage,
    clearError,
  };
}
