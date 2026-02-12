"use client";

import { ModelSelector } from "@/features/model-selector/components/ModelSelector";
import { PromptTypes } from "@/shared/lib/prompt-types";
import type { ConversationCostResponse, ConversationDetail } from "@/types";
import { useState } from "react";
import { DollarSign, ExternalLink, GitBranch, MessageSquare } from "lucide-react";
import { detectPlatform } from "@/shared/utils/platform-detection";

import { useConversationContext } from "../context/ConversationContext";
import { useConversationActions } from "../hooks/useConversationActions";
import { DeleteConfirmModal } from "./DeleteConfirmModal";
import { CostDetailModal } from "./CostDetailModal";
import { TitleEditor } from "./TitleEditor";
import { type ViewMode } from "./ViewModeTabs";

interface ConversationHeaderProps {
  conversation: ConversationDetail;
  onConversationDeleted?: () => void;
  onTitleUpdated?: (updatedConversation: ConversationDetail) => void;
  viewMode: ViewMode;
  onViewModeChange: (mode: ViewMode) => void;
  costDetails: ConversationCostResponse | null;
}

export function ConversationHeader({
  conversation,
  onConversationDeleted,
  onTitleUpdated,
  costDetails,
}: ConversationHeaderProps) {
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [isEditingTitle, setIsEditingTitle] = useState(false);
  const [editTitle, setEditTitle] = useState("");
  const [showCostModal, setShowCostModal] = useState(false);

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
  } = useConversationContext();

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

  const handleShowCost = (): void => {
    setShowCostModal(true);
  };

  return (
    <div className="flex flex-col gap-3 mb-4 md:mb-6 sm:flex-row sm:items-center sm:justify-between sm:gap-4">
      {/* Title Section - Takes priority on mobile */}
      <div className="flex flex-col gap-1 min-w-0 flex-1">
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
        {conversation.parent_run_id && (
          <div className="flex items-center gap-1.5 text-xs text-slate-400">
            <GitBranch className="w-3 h-3 flex-shrink-0" />
            <span>Seeded from</span>
            <a
              href={`/research/${conversation.parent_run_id}`}
              className="text-emerald-400 hover:text-emerald-300 hover:underline"
            >
              parent run
            </a>
          </div>
        )}
        {(() => {
          const platform = detectPlatform(conversation.url);
          if (!platform) return null;
          return (
            <div className="flex items-center gap-1.5 text-xs text-slate-400">
              <MessageSquare className="w-3 h-3" />
              <span>Imported from</span>
              <a
                href={conversation.url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-400 hover:text-blue-300 hover:underline inline-flex items-center gap-1"
              >
                {platform.displayName}
                <ExternalLink className="w-3 h-3" />
              </a>
            </div>
          );
        })()}
      </div>

      {/* Model Selector - Wraps on mobile */}
      <div className="flex items-center gap-2 flex-wrap sm:flex-nowrap">
        {costDetails && (
          <button
            onClick={handleShowCost}
            className="flex items-center space-x-1 px-2 py-1.5 text-xs font-medium text-[var(--primary-700)] hover:bg-[var(--muted)] rounded border border-[var(--border)] transition-colors"
            title="View conversation costs"
            aria-label="View conversation costs"
          >
            <DollarSign className="w-4 h-4 flex-shrink-0" />
            <span className="hidden xs:inline">Cost</span>
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

      <CostDetailModal
        isOpen={showCostModal}
        onClose={() => setShowCostModal(false)}
        cost={costDetails}
        isLoading={costDetails === null}
      />
    </div>
  );
}
