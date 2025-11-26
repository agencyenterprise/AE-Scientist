"use client";

import React, { useState } from "react";

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
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M6 18L18 6M6 6l12 12"
                />
              </svg>
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
                  <svg
                    className="w-5 h-5 text-[var(--warning)]"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.732 16c-.77.833.192 2.5 1.732 2.5z"
                    />
                  </svg>
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
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-[var(--success-foreground)] mr-2"></div>
                Creating Project...
              </>
            ) : (
              <>
                <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M12 6v6m0 0v6m0-6h6m-6 0H6"
                  />
                </svg>
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
