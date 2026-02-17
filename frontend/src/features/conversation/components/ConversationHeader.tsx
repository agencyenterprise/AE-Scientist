"use client";

import type { ConversationCostResponse, ConversationDetail } from "@/types";
import { useState } from "react";
import { DollarSign, ExternalLink, GitBranch, MessageSquare, Rocket } from "lucide-react";
import { detectPlatform } from "@/shared/utils/platform-detection";

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
    <div className="mb-2 relative">
      {/* Title row with cost button */}
      <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between sm:gap-3 relative z-10">
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

        {/* Cost button - hidden on mobile since balance is in floating nav menu */}
        {costDetails && (
          <button
            onClick={handleShowCost}
            className="hidden sm:flex items-center space-x-1 px-2 py-1.5 text-xs font-medium text-[var(--primary-700)] hover:bg-[var(--muted)] rounded border border-[var(--border)] transition-colors flex-shrink-0"
            title="View conversation costs"
            aria-label="View conversation costs"
          >
            <DollarSign className="w-4 h-4 flex-shrink-0" />
            <span>Cost</span>
          </button>
        )}
      </div>

      {/* Workflow banner - absolutely positioned over right panel area, same vertical level as title */}
      <div className="hidden md:block absolute top-0 left-0 right-0 pointer-events-none">
        <div className="flex">
          {/* Spacer for left panel (2/5 width + gap) */}
          <div className="w-2/5 flex-shrink-0" />
          <div className="w-3 flex-shrink-0" />
          {/* Banner centered in right panel area (3/5 width) */}
          <div className="flex-1 flex justify-center pointer-events-auto">
            <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-emerald-500/10 border border-emerald-500/20">
              <Rocket className="h-3.5 w-3.5 text-emerald-400" />
              <span className="text-xs text-emerald-300">
                Review your project and launch research when ready
              </span>
            </div>
          </div>
        </div>
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
