"use client";

import { ModelSelector } from "@/features/model-selector/components/ModelSelector";
import { PromptTypes } from "@/shared/lib/prompt-types";
import type { ConversationDetail } from "@/types";
import React, { useEffect, useState } from "react";
import { Settings } from "lucide-react";

import { useConversationContext } from "../context/ConversationContext";
import { useConversationActions } from "../hooks/useConversationActions";
import { DeleteConfirmModal } from "./DeleteConfirmModal";
import { TitleEditor } from "./TitleEditor";
import { type ViewMode } from "./ViewModeTabs";

interface ConversationHeaderProps {
  conversation: ConversationDetail;
  onConversationDeleted?: () => void;
  onTitleUpdated?: (updatedConversation: ConversationDetail) => void;
  viewMode: ViewMode;
  onViewModeChange: (mode: ViewMode) => void;
}

export function ConversationHeader({
  conversation,
  onConversationDeleted,
  onTitleUpdated,
  viewMode,
}: ConversationHeaderProps) {
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [isEditingTitle, setIsEditingTitle] = useState(false);
  const [editTitle, setEditTitle] = useState("");
  const [pendingView, setPendingView] = useState<ViewMode | null>(null);

  const { isDeleting, isUpdatingTitle, deleteConversation, updateTitle } = useConversationActions();

  // Get model selection state from context
  const {
    selectedModel,
    selectedProvider,
    effectiveCapabilities,
    isReadOnly,
    isStreaming,
    handleModelChange,
    handleModelDefaults,
    handleModelCapabilities,
    onOpenPromptModal,
  } = useConversationContext();

  useEffect(() => {
    if (pendingView && viewMode === pendingView) {
      setPendingView(null);
    }
  }, [viewMode, pendingView]);

  const handleDeleteConversation = async (): Promise<void> => {
    const success = await deleteConversation(conversation.id);
    if (success) {
      setShowDeleteConfirm(false);
      onConversationDeleted?.();
    }
  };

  const handleStartEdit = (): void => {
    setEditTitle(conversation.title);
    setIsEditingTitle(true);
  };

  const handleCancelEdit = (): void => {
    setIsEditingTitle(false);
    setEditTitle("");
  };

  const handleSaveTitle = async (): Promise<void> => {
    if (!editTitle.trim()) return;

    const trimmedTitle = editTitle.trim();
    if (trimmedTitle === conversation.title) {
      handleCancelEdit();
      return;
    }

    const updatedConversation = await updateTitle(conversation.id, trimmedTitle);
    if (updatedConversation) {
      setIsEditingTitle(false);
      setEditTitle("");
      onTitleUpdated?.(updatedConversation);
    }
  };

  return (
    <div className="flex flex-row items-center justify-between gap-4 mb-4 md:mb-6">
      <TitleEditor
        title={conversation.title}
        isEditing={isEditingTitle}
        editValue={editTitle}
        isUpdating={isUpdatingTitle}
        isDeleting={isDeleting}
        onEditValueChange={setEditTitle}
        onStartEdit={handleStartEdit}
        onSave={handleSaveTitle}
        onCancel={handleCancelEdit}
        onDelete={() => setShowDeleteConfirm(true)}
      />

      {/* Model Selector and AI Config */}
      <div className="flex items-center gap-2">
        {onOpenPromptModal && !isReadOnly && (
          <button
            onClick={onOpenPromptModal}
            className="flex items-center space-x-1 px-2 py-1 text-xs font-medium text-[var(--primary-700)] hover:bg-[var(--muted)] rounded border border-[var(--border)] transition-colors"
            title="Configure AI prompts"
          >
            <Settings className="w-4 h-4" />
            <span>AI Config</span>
          </button>
        )}
        <ModelSelector
          promptType={PromptTypes.IDEA_CHAT}
          onModelChange={handleModelChange}
          onDefaultsChange={handleModelDefaults}
          onCapabilitiesChange={handleModelCapabilities}
          selectedModel={selectedModel}
          selectedProvider={selectedProvider}
          disabled={isReadOnly || isStreaming}
          showMakeDefault={true}
          conversationCapabilities={effectiveCapabilities}
        />
      </div>

      <DeleteConfirmModal
        isOpen={showDeleteConfirm}
        title={conversation.title}
        isDeleting={isDeleting}
        onConfirm={handleDeleteConversation}
        onCancel={() => setShowDeleteConfirm(false)}
      />
    </div>
  );
}
