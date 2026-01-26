import React, { useState, useEffect } from "react";
import { X, Save, Eye, Code } from "lucide-react";
import { Markdown } from "@/shared/components/Markdown";

interface MarkdownEditModalProps {
  isOpen: boolean;
  onClose: () => void;
  content: string;
  onSave: (content: string) => Promise<void>;
  isSaving: boolean;
}

export function MarkdownEditModal({
  isOpen,
  onClose,
  content,
  onSave,
  isSaving,
}: MarkdownEditModalProps): React.JSX.Element | null {
  const [editedContent, setEditedContent] = useState(content);
  const [viewMode, setViewMode] = useState<"edit" | "preview">("edit");

  useEffect(() => {
    setEditedContent(content);
  }, [content]);

  if (!isOpen) return null;

  const handleSave = async () => {
    await onSave(editedContent);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Escape") {
      onClose();
    }
    if ((e.metaKey || e.ctrlKey) && e.key === "s") {
      e.preventDefault();
      handleSave();
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      onClick={onClose}
    >
      <div
        className="flex h-[90vh] w-full max-w-6xl flex-col rounded-lg bg-zinc-900 border border-zinc-700 shadow-xl"
        onClick={e => e.stopPropagation()}
        onKeyDown={handleKeyDown}
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-zinc-700 px-6 py-4">
          <h2 className="text-xl font-semibold text-white">Edit Research Idea</h2>
          <div className="flex items-center gap-2">
            {/* View Mode Toggle */}
            <div className="flex rounded-lg border border-zinc-600 bg-zinc-800">
              <button
                onClick={() => setViewMode("edit")}
                className={`flex items-center gap-2 px-3 py-1.5 text-sm font-medium transition-colors ${
                  viewMode === "edit" ? "bg-blue-600 text-white" : "text-zinc-300 hover:text-white"
                }`}
              >
                <Code className="h-4 w-4" />
                Edit
              </button>
              <button
                onClick={() => setViewMode("preview")}
                className={`flex items-center gap-2 px-3 py-1.5 text-sm font-medium transition-colors ${
                  viewMode === "preview"
                    ? "bg-blue-600 text-white"
                    : "text-zinc-300 hover:text-white"
                }`}
              >
                <Eye className="h-4 w-4" />
                Preview
              </button>
            </div>

            <button
              onClick={onClose}
              className="rounded-lg p-2 text-zinc-400 transition-colors hover:bg-zinc-800 hover:text-white"
              aria-label="Close"
            >
              <X className="h-5 w-5" />
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-hidden p-6">
          {viewMode === "edit" ? (
            <textarea
              value={editedContent}
              onChange={e => setEditedContent(e.target.value)}
              className="h-full w-full resize-none rounded-lg border border-zinc-700 bg-zinc-800 p-4 font-mono text-sm text-white placeholder-zinc-500 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
              placeholder="Write your research idea in markdown format..."
              autoFocus
            />
          ) : (
            <div className="h-full overflow-y-auto rounded-lg border border-zinc-700 bg-zinc-800 p-6">
              <Markdown>{editedContent}</Markdown>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between border-t border-zinc-700 px-6 py-4">
          <p className="text-sm text-zinc-400">
            Press <kbd className="rounded bg-zinc-800 px-1.5 py-0.5 text-xs">Esc</kbd> to cancel,{" "}
            <kbd className="rounded bg-zinc-800 px-1.5 py-0.5 text-xs">Cmd+S</kbd> to save
          </p>
          <div className="flex gap-3">
            <button
              onClick={onClose}
              disabled={isSaving}
              className="rounded-lg border border-zinc-600 px-4 py-2 text-sm font-medium text-zinc-300 transition-colors hover:bg-zinc-800 disabled:cursor-not-allowed disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              onClick={handleSave}
              disabled={isSaving || editedContent === content}
              className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <Save className="h-4 w-4" />
              {isSaving ? "Saving..." : "Save Changes"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
