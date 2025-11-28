"use client";

import React, { useState } from "react";
import { X, AlertTriangle, Loader2, Plus } from "lucide-react";

interface CreateProjectModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => Promise<void>;
  isLoading?: boolean;
}

export function CreateProjectModal({
  isOpen,
  onClose,
  onConfirm,
  isLoading = false,
}: CreateProjectModalProps) {
  const [error, setError] = useState("");

  const handleConfirm = async () => {
    setError("");
    try {
      await onConfirm();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create project");
    }
  };

  const handleClose = () => {
    if (!isLoading) {
      setError("");
      onClose();
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black bg-opacity-50">
      <div className="relative bg-card rounded-lg shadow-xl max-w-md w-full">
        <div className="p-6">
          {/* Header */}
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-medium text-foreground">Create Linear Project</h3>
            <button
              type="button"
              onClick={handleClose}
              disabled={isLoading}
              className="text-muted-foreground hover:text-foreground disabled:opacity-50 p-1 rounded"
            >
              <X className="w-6 h-6" />
            </button>
          </div>

          {/* Content */}
          <div className="mb-6">
            <p className="text-sm text-muted-foreground mb-4">
              This will create a new project in Linear using your current project draft.
            </p>

            {/* Warning */}
            <div className="bg-[color-mix(in_srgb,var(--warning),transparent_90%)] border border-[var(--warning)] rounded-lg p-4">
              <div className="flex">
                <div className="flex-shrink-0">
                  <AlertTriangle className="w-5 h-5 text-[var(--warning)]" />
                </div>
                <div className="ml-3">
                  <h3 className="text-sm font-medium text-foreground">Important</h3>
                  <div className="mt-1 text-sm text-muted-foreground">
                    <p>
                      Once created, this conversation will be locked and you won&apos;t be able to
                      modify the project draft or continue the AI chat. This action cannot be
                      undone.
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Error Message */}
          {error && (
            <div className="mb-4 p-3 bg-[color-mix(in_srgb,var(--danger),transparent_90%)] border border-[var(--danger)] rounded-md">
              <p className="text-sm text-[var(--danger)]">{error}</p>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="bg-muted px-6 py-3 flex flex-row-reverse gap-3">
          <button
            onClick={handleConfirm}
            disabled={isLoading}
            className="inline-flex items-center justify-center px-4 py-2 bg-[var(--success)] text-[var(--success-foreground)] text-sm font-medium rounded-md hover:opacity-90 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-[var(--success)] disabled:bg-muted disabled:text-muted-foreground disabled:cursor-not-allowed"
          >
            {isLoading ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                Creating Project...
              </>
            ) : (
              <>
                <Plus className="w-4 h-4 mr-2" />
                Create Project
              </>
            )}
          </button>
          <button
            onClick={handleClose}
            disabled={isLoading}
            className="inline-flex items-center justify-center px-4 py-2 bg-[var(--surface)] text-[var(--foreground)]/80 text-sm font-medium border border-[var(--border)] rounded-md hover:bg-[var(--muted)] focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-[var(--ring)] disabled:opacity-50"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}
