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
      className="fixed inset-0 z-50 flex md:items-center md:justify-center bg-black/50 md:p-4"
      onClick={onClose}
    >
      <div
        className="flex h-full w-full md:h-[90vh] md:max-w-6xl flex-col bg-zinc-900 md:rounded-lg border-0 md:border border-zinc-700 shadow-xl"
        onClick={e => e.stopPropagation()}
        onKeyDown={handleKeyDown}
      >
        {/* Header - compact on mobile */}
        <div className="flex items-center justify-between border-b border-zinc-700 px-3 py-2 md:px-6 md:py-4">
          <h2 className="text-base md:text-xl font-semibold text-white">Edit Idea</h2>
          <div className="flex items-center gap-2">
            {/* View Mode Toggle */}
            <div className="flex rounded-md border border-zinc-600 bg-zinc-800">
              <button
                onClick={() => setViewMode("edit")}
                className={`flex items-center gap-1 px-2 py-1 text-xs font-medium transition-colors md:gap-2 md:px-3 md:py-1.5 md:text-sm ${
                  viewMode === "edit" ? "bg-blue-600 text-white" : "text-zinc-300 hover:text-white"
                }`}
              >
                <Code className="h-3.5 w-3.5 md:h-4 md:w-4" />
                Edit
              </button>
              <button
                onClick={() => setViewMode("preview")}
                className={`flex items-center gap-1 px-2 py-1 text-xs font-medium transition-colors md:gap-2 md:px-3 md:py-1.5 md:text-sm ${
                  viewMode === "preview"
                    ? "bg-blue-600 text-white"
                    : "text-zinc-300 hover:text-white"
                }`}
              >
                <Eye className="h-3.5 w-3.5 md:h-4 md:w-4" />
                Preview
              </button>
            </div>

            <button
              onClick={onClose}
              className="rounded-lg p-1.5 md:p-2 text-zinc-400 transition-colors hover:bg-zinc-800 hover:text-white"
              aria-label="Close"
            >
              <X className="h-5 w-5" />
            </button>
          </div>
        </div>

        {/* Content - minimal padding on mobile for maximum editing space */}
        <div className="flex-1 min-h-0 p-2 md:p-6 overflow-hidden">
          {viewMode === "edit" ? (
            <textarea
              value={editedContent}
              onChange={e => setEditedContent(e.target.value)}
              className="h-full w-full resize-none rounded-md border border-zinc-700 bg-zinc-800 p-2 md:p-4 font-mono text-base md:text-sm leading-relaxed text-white placeholder-zinc-500 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
              placeholder="Write your research idea in markdown format..."
              autoFocus
            />
          ) : (
            <div className="h-full overflow-y-auto overflow-x-hidden rounded-md border border-zinc-700 bg-zinc-800 p-3 md:p-6">
              <div className="[overflow-wrap:anywhere]">
                <Markdown>{editedContent}</Markdown>
              </div>
            </div>
          )}
        </div>

        {/* Footer - compact on mobile */}
        <div className="flex items-center justify-between border-t border-zinc-700 px-3 py-2 md:px-6 md:py-4">
          <p className="hidden text-sm text-zinc-400 md:block">
            Press <kbd className="rounded bg-zinc-800 px-1.5 py-0.5 text-xs">Esc</kbd> to cancel,{" "}
            <kbd className="rounded bg-zinc-800 px-1.5 py-0.5 text-xs">Cmd+S</kbd> to save
          </p>
          <div className="flex w-full gap-2 md:w-auto md:gap-3">
            <button
              onClick={onClose}
              disabled={isSaving}
              className="flex-1 rounded-md border border-zinc-600 px-3 py-1.5 text-sm font-medium text-zinc-300 transition-colors hover:bg-zinc-800 disabled:cursor-not-allowed disabled:opacity-50 md:flex-none md:px-4 md:py-2"
            >
              Cancel
            </button>
            <button
              onClick={handleSave}
              disabled={isSaving || editedContent === content}
              className="flex-1 inline-flex items-center justify-center gap-1.5 rounded-md bg-blue-600 px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50 md:flex-none md:gap-2 md:px-4 md:py-2"
            >
              <Save className="h-4 w-4" />
              {isSaving ? "Saving..." : "Save"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
