"use client";

import React, { useCallback, useEffect } from "react";

import { PromptEditModal } from "@/features/project-draft/components/PromptEditModal";
import { PromptTypes } from "@/shared/lib/prompt-types";

import { useConversationImport } from "../hooks/useConversationImport";
import { usePromptModal } from "../hooks/usePromptModal";
import { ConflictResolution } from "./ConflictResolution";
import { ImportForm } from "./ImportForm";
import { ImportStreamingCard } from "./ImportStreamingCard";
import { ModelLimitConflict } from "./ModelLimitConflict";

export interface ImportModalProps {
  isOpen: boolean;
  onClose: () => void;
  isLoading?: boolean;
  onImportStart?: () => void;
  onImportEnd?: () => void;
}

/**
 * Modal wrapper for the conversation import flow.
 * Uses the reusable useConversationImport hook and composes presentational components.
 */
export function ImportModal({
  isOpen,
  onClose,
  isLoading = false,
  onImportStart,
  onImportEnd,
}: ImportModalProps) {
  const importState = useConversationImport({
    onImportStart,
    onImportEnd,
    onSuccess: id => {
      onClose();
      window.location.href = `/conversations/${id}`;
    },
    autoRedirect: false, // We handle redirect in onSuccess
  });

  const promptModal = usePromptModal();

  // Handle close with state check
  const handleClose = useCallback(() => {
    if (!isLoading && !importState.status.isImporting) {
      importState.actions.reset();
      onClose();
    }
  }, [isLoading, importState.status.isImporting, importState.actions, onClose]);

  // Handle escape key
  useEffect(() => {
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") handleClose();
    };

    if (isOpen) {
      document.addEventListener("keydown", handleEscape);
      return () => document.removeEventListener("keydown", handleEscape);
    }
    return undefined;
  }, [isOpen, handleClose]);

  if (!isOpen) return null;

  return (
    <>
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black bg-opacity-50">
        <div
          className={`relative bg-card rounded-lg shadow-xl w-full max-h-[90vh] overflow-auto ${
            importState.status.isImporting ? "max-w-3xl" : "max-w-2xl"
          }`}
        >
          {importState.status.hasConflict ? (
            <ConflictResolution
              conflicts={importState.conflict.items}
              selectedConflictId={importState.conflict.selectedId}
              onSelectConflict={importState.actions.selectConflict}
              onGoToSelected={importState.actions.resolveConflictGoTo}
              onUpdateSelected={importState.actions.resolveConflictUpdate}
              onCreateNew={importState.actions.resolveConflictCreateNew}
              onCancel={importState.actions.cancelConflict}
              onClose={handleClose}
            />
          ) : importState.status.hasModelLimitConflict ? (
            <ModelLimitConflict
              message={importState.modelLimit.message}
              suggestion={importState.modelLimit.suggestion}
              onProceed={importState.actions.proceedWithSummarization}
              onCancel={importState.actions.cancelModelLimit}
              onClose={handleClose}
            />
          ) : importState.status.isImporting ? (
            <ImportStreamingCard
              streamingContent={importState.state.streamingContent}
              currentState={importState.state.currentState}
              summaryProgress={importState.state.summaryProgress}
              isUpdateMode={importState.state.isUpdateMode}
              textareaRef={importState.streamingRef}
              showHeader={true}
              onClose={handleClose}
            />
          ) : (
            <ImportForm
              url={importState.state.url}
              onUrlChange={importState.actions.setUrl}
              error={importState.state.error}
              model={importState.model}
              onModelChange={importState.actions.setModel}
              onModelDefaults={importState.actions.setModelDefaults}
              onSubmit={importState.actions.startImport}
              onShowPromptModal={promptModal.open}
              onClose={handleClose}
              isDisabled={isLoading}
              isSubmitting={importState.status.isImporting}
              variant="modal"
            />
          )}
        </div>
      </div>

      <PromptEditModal
        isOpen={promptModal.isOpen}
        onClose={promptModal.close}
        promptType={PromptTypes.IDEA_GENERATION}
      />
    </>
  );
}

export default ImportModal;
