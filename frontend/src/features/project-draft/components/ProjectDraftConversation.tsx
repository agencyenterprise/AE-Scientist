"use client";

import { useRef, useState, useCallback, useEffect } from "react";

import { useConversationContext } from "@/features/conversation/context/ConversationContext";
import type { Idea, FileMetadata } from "@/types";
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
  isLocked: boolean;
  currentProjectDraft?: Idea | null;
  onProjectDraftUpdate?: (updatedDraft: Idea) => void;
  onOpenPromptModal?: () => void;
  onConversationLocked?: () => void;
  conversationCapabilities?: {
    hasImages?: boolean;
    hasPdfs?: boolean;
  };
  isVisible: boolean;
  onAnswerFinish?: () => void;
}

export function ProjectDraftConversation({
  conversationId,
  isLocked,
  currentProjectDraft,
  onProjectDraftUpdate,
  onOpenPromptModal,
  onConversationLocked,
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
    onConversationLocked,
    consumePendingFiles,
    restorePendingFiles,
    inputRef,
    onStreamEnd: onAnswerFinish,
  });

  // Sync isStreaming to context
  useEffect(() => {
    setIsStreaming(isStreaming);
  }, [isStreaming, setIsStreaming]);

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
