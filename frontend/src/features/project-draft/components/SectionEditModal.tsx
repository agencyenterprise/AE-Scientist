"use client";

import { useState, useEffect } from "react";
import { createPortal } from "react-dom";
import { X } from "lucide-react";

interface SectionEditModalProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  content: string;
  onSave: (newContent: string) => Promise<void>;
  isSaving?: boolean;
}

export function SectionEditModal({
  isOpen,
  onClose,
  title,
  content,
  onSave,
  isSaving = false,
}: SectionEditModalProps): React.JSX.Element | null {
  const [editContent, setEditContent] = useState<string>(content);
  const [error, setError] = useState<string>("");
  const [isClient, setIsClient] = useState<boolean>(false);

  useEffect(() => {
    setIsClient(true);
  }, []);

  // Reset content when modal opens with new content
  useEffect(() => {
    if (isOpen) {
      setEditContent(content);
      setError("");
    }
  }, [isOpen, content]);

  const handleSave = async (): Promise<void> => {
    if (!editContent.trim()) {
      setError("Content cannot be empty");
      return;
    }

    setError("");

    try {
      await onSave(editContent.trim());
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save");
    }
  };

  const handleKeyDown = (event: React.KeyboardEvent): void => {
    if (event.key === "Escape") {
      onClose();
    } else if (event.key === "Enter" && event.ctrlKey) {
      handleSave();
    }
  };

  const handleClose = (): void => {
    setError("");
    setEditContent("");
    onClose();
  };

  if (!isOpen || !isClient) return null;

  return createPortal(
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black bg-opacity-50">
      <div className="relative bg-card rounded-lg p-4 sm:p-6 w-full sm:max-w-3xl max-h-[90vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-semibold text-foreground">Edit {title}</h2>
          <button
            onClick={handleClose}
            className="text-muted-foreground hover:text-foreground p-1 rounded-md hover:bg-muted transition-colors"
            disabled={isSaving}
            aria-label="Close modal"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Error message */}
        {error && (
          <div className="mb-4 p-3 bg-destructive/10 border border-destructive/30 text-destructive rounded text-sm">
            {error}
          </div>
        )}

        {/* Content */}
        <div className="flex-1 overflow-hidden flex flex-col min-h-0">
          <label
            htmlFor="section-content-editor"
            className="block text-sm font-medium text-muted-foreground mb-2"
          >
            Content (Markdown supported)
          </label>
          <textarea
            id="section-content-editor"
            value={editContent}
            onChange={e => setEditContent(e.target.value)}
            onKeyDown={handleKeyDown}
            className="flex-1 min-h-[400px] sm:min-h-[50vh] w-full p-3 border border-border rounded-md resize-y focus:ring-2 focus:ring-ring focus:border-ring bg-surface text-foreground font-mono text-sm"
            placeholder="Enter content..."
            disabled={isSaving}
            autoFocus
          />
          <p className="mt-2 text-xs text-muted-foreground">
            Press Ctrl+Enter to save, Escape to cancel
          </p>
        </div>

        {/* Footer */}
        <div className="flex justify-end gap-3 mt-6 pt-4 border-t border-border">
          <button
            onClick={handleClose}
            disabled={isSaving}
            className="px-4 py-2 text-sm font-medium text-foreground bg-muted hover:bg-muted/80 rounded-md disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={isSaving || !editContent.trim()}
            className="px-4 py-2 text-sm font-medium text-primary-foreground bg-primary hover:bg-primary-hover rounded-md disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {isSaving ? "Saving..." : "Save"}
          </button>
        </div>
      </div>
    </div>,
    document.body
  );
}
