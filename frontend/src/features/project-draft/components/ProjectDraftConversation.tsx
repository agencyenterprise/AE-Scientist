"use client";

import { useRef, useState, useCallback, useEffect } from "react";

import { useConversationContext } from "@/features/conversation/context/ConversationContext";
import type { Idea, FileMetadata, ConversationDetail } from "@/types";
import { useAuth } from "@/shared/hooks/useAuth";

import { isIdeaGenerating } from "../utils/versionUtils";
import { useChatMessages } from "../hooks/useChatMessages";
import { useChatFileUpload } from "../hooks/useChatFileUpload";
import { useChatStreaming } from "../hooks/useChatStreaming";

import { ChatMessageList } from "./ChatMessageList";
import { ChatInputArea } from "./ChatInputArea";
import { ChatGeneratingState } from "./ChatGeneratingState";

interface ProjectDraftConversationProps {
  conversationId: number;
  conversation: ConversationDetail;
  isLocked: boolean;
  currentProjectDraft?: Idea | null;
  onProjectDraftUpdate?: (updatedDraft: Idea) => void;
  onOpenPromptModal?: () => void;
  conversationCapabilities?: {
    hasImages?: boolean;
    hasPdfs?: boolean;
  };
  isVisible: boolean;
  onAnswerFinish?: () => void;
}

export function ProjectDraftConversation({
  conversationId,
  conversation,
  isLocked,
  currentProjectDraft,
  onProjectDraftUpdate,
  onOpenPromptModal,
  conversationCapabilities,
  isVisible,
  onAnswerFinish,
}: ProjectDraftConversationProps) {
  const { user } = useAuth();

  // Ensure user is authenticated for chat functionality
  if (!user) {
    throw new Error("User must be authenticated to use chat functionality");
  }

  const inputRef = useRef<HTMLTextAreaElement>(null);
  const [inputMessage, setInputMessage] = useState("");
  const hasAutoTriggeredRef = useRef(false);

  // Check if project draft is currently being generated
  const isGenerating = isIdeaGenerating(currentProjectDraft || null);
  const isReadOnly = isLocked || isGenerating;

  // Get model selection from context (lifted to ConversationView level)
  const {
    currentModel,
    currentProvider,
    modelCapabilities,
    setEffectiveCapabilities,
    setIsStreaming,
    setIsReadOnly,
    setOnOpenPromptModal,
  } = useConversationContext();

  // Custom hooks for state management
  const { messages, setMessages, isLoadingHistory } = useChatMessages({ conversationId });

  const {
    pendingFiles,
    showFileUpload,
    effectiveCapabilities,
    handleFilesUploaded,
    removePendingFile,
    clearPendingFiles,
    toggleFileUpload,
    consumePendingFiles,
  } = useChatFileUpload({ conversationCapabilities, messages });

  // Sync dynamic state to context so header can read it
  useEffect(() => {
    setEffectiveCapabilities(effectiveCapabilities);
  }, [effectiveCapabilities, setEffectiveCapabilities]);

  useEffect(() => {
    setIsReadOnly(isReadOnly);
  }, [isReadOnly, setIsReadOnly]);

  useEffect(() => {
    setOnOpenPromptModal(onOpenPromptModal);
  }, [onOpenPromptModal, setOnOpenPromptModal]);

  // Restore pending files callback for error recovery
  const restorePendingFiles = useCallback(
    (files: FileMetadata[]) => {
      // We need to manually add files back - using a workaround since we can't directly set
      files.forEach(file => handleFilesUploaded([file]));
    },
    [handleFilesUploaded]
  );

  const { isStreaming, streamingContent, statusMessage, error, sendMessage } = useChatStreaming({
    conversationId,
    user,
    currentModel,
    currentProvider,
    messages,
    setMessages,
    onProjectDraftUpdate,
    consumePendingFiles,
    restorePendingFiles,
    inputRef,
    onStreamEnd: onAnswerFinish,
  });

  // Sync isStreaming to context
  useEffect(() => {
    setIsStreaming(isStreaming);
  }, [isStreaming, setIsStreaming]);

  // Auto-trigger streaming for seeded conversations with unanswered review feedback
  useEffect(() => {
    // Check if already triggered
    if (hasAutoTriggeredRef.current) return;

    // Check if conversation is seeded from a research run
    const isSeededFromRun = conversation.url.startsWith("seeded://run/");
    if (!isSeededFromRun) return;

    // Wait for messages to load
    if (isLoadingHistory) return;

    // Check if there are messages
    if (messages.length === 0) return;

    // Check if last message is from user (unanswered)
    const lastMessage = messages[messages.length - 1];
    const hasUnansweredUserMessage = lastMessage && lastMessage.role === "user";
    if (!hasUnansweredUserMessage) return;

    // Check if model is ready
    if (!currentModel || !currentProvider) return;

    // Check if not already streaming
    if (isStreaming) return;

    // Mark as triggered and auto-send the last user message
    hasAutoTriggeredRef.current = true;

    // Auto-trigger streaming response to the user's message
    sendMessage(lastMessage.content);
  }, [
    conversation.url,
    isLoadingHistory,
    messages,
    currentModel,
    currentProvider,
    isStreaming,
    sendMessage,
  ]);

  const handleSendMessage = useCallback(async () => {
    if (!inputMessage.trim() && pendingFiles.length === 0) return;

    const message = inputMessage;
    setInputMessage("");

    // Reset textarea height when sending message
    if (inputRef.current) {
      inputRef.current.style.height = "auto";
    }

    await sendMessage(message);
  }, [inputMessage, pendingFiles.length, sendMessage]);

  return (
    <div className="flex flex-col h-full max-w-full overflow-x-hidden">
      {/* Messages Area */}
      <ChatMessageList
        messages={messages}
        isLoadingHistory={isLoadingHistory}
        isStreaming={isStreaming}
        streamingContent={streamingContent}
        statusMessage={statusMessage}
        isVisible={isVisible}
      />

      {/* Input Area or Generating Message (lock banner is rendered by parent tab) */}
      {isReadOnly ? (
        isLocked ? null : (
          <ChatGeneratingState />
        )
      ) : (
        <ChatInputArea
          conversationId={conversationId}
          error={error}
          showFileUpload={showFileUpload}
          pendingFiles={pendingFiles}
          inputMessage={inputMessage}
          isLoadingHistory={isLoadingHistory}
          isStreaming={isStreaming}
          currentModel={currentModel}
          currentProvider={currentProvider}
          modelCapabilities={modelCapabilities}
          onFilesUploaded={handleFilesUploaded}
          onClearAllFiles={clearPendingFiles}
          onRemoveFile={removePendingFile}
          onInputChange={setInputMessage}
          onSendMessage={handleSendMessage}
          onToggleFileUpload={toggleFileUpload}
          inputRef={inputRef}
        />
      )}
    </div>
  );
}
