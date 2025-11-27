"use client";

import React, { useEffect, useState } from "react";

import type { ConversationDetail } from "@/types";

import { useConversationActions } from "../hooks/useConversationActions";
import { DeleteConfirmModal } from "./DeleteConfirmModal";
import { TitleEditor } from "./TitleEditor";
import { ViewModeTabs, type ViewMode } from "./ViewModeTabs";

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
  onViewModeChange,
}: ConversationHeaderProps) {
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [isEditingTitle, setIsEditingTitle] = useState(false);
  const [editTitle, setEditTitle] = useState("");
  const [pendingView, setPendingView] = useState<ViewMode | null>(null);

  const { isDeleting, isUpdatingTitle, deleteConversation, updateTitle } = useConversationActions();

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

  const handleViewChange = (mode: ViewMode): void => {
    if (viewMode === mode) return;
    setPendingView(mode);
    onViewModeChange(mode);
  };

  return (
    <>
      <div className="toolbar-glass">
        <div className="px-6 py-2">
          <div className="flex items-center justify-between">
            <div className="flex-1 min-w-0">
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
            </div>

            <div className="flex items-center space-x-2 ml-4 flex-shrink-0">
              <ViewModeTabs
                viewMode={viewMode}
                pendingView={pendingView}
                onViewChange={handleViewChange}
              />
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
    </>
  );
}
