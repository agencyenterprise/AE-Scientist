import { useRef, useEffect } from "react";

import type { ChatMessage as ChatMessageType } from "@/types";

import { ChatEmptyState } from "./ChatEmptyState";
import { ChatLoadingState } from "./ChatLoadingState";
import { ChatMessage } from "./ChatMessage";
import { ChatStreamingMessage } from "./ChatStreamingMessage";

interface ChatMessageListProps {
  messages: ChatMessageType[];
  isLoadingHistory: boolean;
  isStreaming: boolean;
  streamingContent: string;
  statusMessage: string;
  isVisible: boolean;
  isPollingEmptyMessage: boolean;
}

export function ChatMessageList({
  messages,
  isLoadingHistory,
  isStreaming,
  streamingContent,
  statusMessage,
  isVisible,
  isPollingEmptyMessage,
}: ChatMessageListProps) {
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when new messages arrive
  const scrollToBottom = (): void => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, streamingContent]);

  // When chat becomes visible (e.g., mobile toggle), ensure we scroll to the latest message
  useEffect(() => {
    let timeoutId: number | null = null;
    if (isVisible) {
      // wait for layout to update after visibility change
      timeoutId = window.setTimeout(() => {
        scrollToBottom();
      }, 0);
    }
    return () => {
      if (timeoutId !== null) {
        clearTimeout(timeoutId);
      }
    };
  }, [isVisible]);

  // Detect if last message is empty assistant message being polled
  const lastMessage = messages.length > 0 ? messages[messages.length - 1] : null;
  const isLastMessageEmptyAssistant =
    lastMessage &&
    lastMessage.role === "assistant" &&
    !lastMessage.content.trim() &&
    isPollingEmptyMessage;

  // Filter out empty assistant message if we're showing loading state for it
  const messagesToRender = isLastMessageEmptyAssistant ? messages.slice(0, -1) : messages;

  return (
    <div
      className={`flex-1 overflow-y-auto px-4 py-4 ${messages.length > 0 || isStreaming ? "space-y-4" : ""} min-h-0 max-w-full overflow-x-hidden`}
    >
      {isLoadingHistory ? (
        <ChatLoadingState />
      ) : messages.length === 0 ? (
        <ChatEmptyState />
      ) : (
        messagesToRender.map((message, index) => (
          <ChatMessage key={`${message.sequence_number}-${index}`} message={message} />
        ))
      )}

      {/* Show loading state for empty assistant message being polled */}
      {isLastMessageEmptyAssistant && (
        <ChatStreamingMessage statusMessage="Generating response..." streamingContent="" />
      )}

      {/* Streaming content */}
      {isStreaming && (
        <ChatStreamingMessage statusMessage={statusMessage} streamingContent={streamingContent} />
      )}

      <div ref={messagesEndRef} />
    </div>
  );
}
