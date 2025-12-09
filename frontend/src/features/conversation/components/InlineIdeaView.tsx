"use client";

import { Eye, FlaskConical, Pencil } from "lucide-react";
import { useRouter } from "next/navigation";
import { Button } from "@/shared/components/ui/button";
import { ProjectDraftContent } from "@/features/project-draft/components/ProjectDraftContent";
import { ProjectDraftSkeleton } from "@/features/project-draft/components/ProjectDraftSkeleton";
import { useSelectedIdeaData } from "../hooks/useSelectedIdeaData";
import { useConversationResearchRuns } from "../hooks/useConversationResearchRuns";
import type { InlineIdeaViewProps } from "../types/ideation-queue.types";

/**
 * Inline view component for displaying idea content in read-only mode.
 * Handles empty, loading, error, and data states.
 *
 * Uses CSS pointer-events-none approach for read-only mode to avoid
 * modifying the ProjectDraftContent component.
 */
export function InlineIdeaView({ conversationId }: InlineIdeaViewProps) {
  const router = useRouter();
  const { idea, isLoading, error, refetch } = useSelectedIdeaData(conversationId);
  const { runs } = useConversationResearchRuns(conversationId ?? 0);

  const handleEditClick = () => {
    if (conversationId) {
      router.push(`/conversations/${conversationId}`);
    }
  };

  // Empty state - no selection
  if (conversationId === null) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center">
        <Eye className="mb-4 h-12 w-12 text-slate-600" />
        <h3 className="mb-1 text-sm font-medium text-slate-300">Select an idea</h3>
        <p className="text-xs text-slate-500">Choose an idea above to preview its details</p>
      </div>
    );
  }

  // Loading state
  if (isLoading) {
    return <ProjectDraftSkeleton />;
  }

  // Error state
  if (error) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center">
        <div className="rounded-lg bg-red-500/10 p-4 text-red-400">
          <p className="text-sm">{error}</p>
          <button onClick={() => refetch()} className="mt-2 text-xs underline hover:no-underline">
            Try again
          </button>
        </div>
      </div>
    );
  }

  // No idea data for this conversation
  if (!idea) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center">
        <Eye className="mb-4 h-12 w-12 text-slate-600" />
        <h3 className="mb-1 text-sm font-medium text-slate-300">No idea yet</h3>
        <p className="text-xs text-slate-500">
          This conversation doesn&apos;t have an idea generated yet
        </p>
      </div>
    );
  }

  // Success state - display read-only content
  const activeVersion = idea.active_version;
  const runCount = runs.length;

  return (
    <div className="relative space-y-6">
      {/* Metadata header */}
      <div className="space-y-4 border-b border-slate-800 pb-6">
        {/* Title */}
        <h2 className="text-2xl font-semibold text-white">
          {activeVersion?.title || "Untitled Idea"}
        </h2>

        <div className="flex flex-row gap-6 items-center">
          {/* Metadata */}
          {activeVersion?.created_at && (
            <div className="text-sm">
              <span className="text-slate-500">Created: </span>
              <span className="text-slate-300">
                {new Date(activeVersion.created_at).toLocaleString()}
              </span>
            </div>
          )}

          {/* Badges */}
          {runCount > 0 && (
            <div className="flex items-center gap-2">
              <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-500/15 px-3 py-1 text-xs font-medium text-emerald-400">
                <FlaskConical className="h-3 w-3" />
                {runCount} {runCount === 1 ? "run" : "runs"}
              </span>
            </div>
          )}

          {/* Edit button */}
          <Button
            onClick={handleEditClick}
            variant="outline"
            size="sm"
            className="ml-auto"
            aria-label="Edit research idea"
          >
            <Pencil className="h-3 w-3 mr-1.5" />
            Edit
          </Button>
        </div>
      </div>

      {/* Content with disabled edit interactions and hidden edit buttons */}
      <div className="[&_button]:hidden [&_textarea]:pointer-events-none [&_input]:pointer-events-none">
        <ProjectDraftContent
          projectDraft={idea}
          conversationId={conversationId.toString()}
          onUpdate={() => {}} // No-op handler for read-only mode
        />
      </div>
    </div>
  );
}
