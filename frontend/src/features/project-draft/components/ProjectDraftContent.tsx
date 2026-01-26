import React, { ReactElement, useState } from "react";
import { Pencil } from "lucide-react";

import type { Idea } from "@/types";

import { isIdeaGenerating } from "../utils/versionUtils";
import { ProjectDraftSkeleton } from "./ProjectDraftSkeleton";
import { Markdown } from "@/shared/components/Markdown";
import { MarkdownEditModal } from "./MarkdownEditModal";

interface ProjectDraftContentProps {
  projectDraft: Idea;
  conversationId: string;
  onUpdate: (updatedIdea: Idea) => void;
  markdownDiffContent?: ReactElement[] | null;
  showDiffs?: boolean;
}

export function ProjectDraftContent({
  projectDraft,
  conversationId,
  onUpdate,
  markdownDiffContent = null,
  showDiffs = false,
}: ProjectDraftContentProps): React.JSX.Element {
  const isGenerating = isIdeaGenerating(projectDraft);
  const activeVersion = projectDraft.active_version;

  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [isSaving, setIsSaving] = useState(false);

  const handleSave = async (updatedMarkdown: string) => {
    setIsSaving(true);
    try {
      const response = await fetch(`/api/conversations/${conversationId}/idea`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ idea_markdown: updatedMarkdown }),
      });

      if (!response.ok) {
        throw new Error("Failed to update idea");
      }

      const data = await response.json();
      if (data.success && data.idea) {
        onUpdate(data.idea);
        setIsEditModalOpen(false);
      }
    } catch (error) {
      // eslint-disable-next-line no-console
      console.error("Error updating idea:", error);
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <>
      <div className="flex-1 flex flex-col min-h-0 overflow-hidden">
        {/* Edit Button */}
        {!isGenerating && activeVersion?.idea_markdown && (
          <div className="flex justify-end px-4 py-2 border-b border-zinc-200 dark:border-zinc-800">
            <button
              onClick={() => setIsEditModalOpen(true)}
              className="inline-flex items-center gap-2 rounded-lg border border-blue-500/40 px-3 py-1.5 text-sm font-medium text-blue-200 transition-colors hover:bg-blue-500/10"
            >
              <Pencil className="h-4 w-4" />
              Edit Idea
            </button>
          </div>
        )}

        {/* Markdown Content */}
        <div className="flex-1 overflow-y-auto px-4 py-6">
          {isGenerating ? (
            <ProjectDraftSkeleton />
          ) : showDiffs && markdownDiffContent ? (
            <div className="prose prose-invert max-w-none">
              <div className="whitespace-pre-wrap font-mono text-sm leading-relaxed">
                {markdownDiffContent}
              </div>
            </div>
          ) : activeVersion?.idea_markdown ? (
            <Markdown className="prose prose-invert max-w-none">
              {activeVersion.idea_markdown}
            </Markdown>
          ) : (
            <p className="text-zinc-400 text-sm">No idea content available.</p>
          )}
        </div>
      </div>

      {/* Markdown Edit Modal */}
      {activeVersion?.idea_markdown && (
        <MarkdownEditModal
          isOpen={isEditModalOpen}
          onClose={() => setIsEditModalOpen(false)}
          content={activeVersion.idea_markdown}
          onSave={handleSave}
          isSaving={isSaving}
        />
      )}
    </>
  );
}
