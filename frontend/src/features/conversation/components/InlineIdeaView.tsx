"use client";

import { Eye, FlaskConical, Pencil } from "lucide-react";
import { useRouter } from "next/navigation";
import { Button } from "@/shared/components/ui/button";
import { ProjectDraftContent } from "@/features/project-draft/components/ProjectDraftContent";
import { ProjectDraftSkeleton } from "@/features/project-draft/components/ProjectDraftSkeleton";
import { useSelectedIdeaData } from "../hooks/useSelectedIdeaData";
import { useConversationResearchRuns } from "../hooks/useConversationResearchRuns";
import { LaunchResearchButton } from "./LaunchResearchButton";
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
  const { runs } = useConversationResearchRuns(conversationId);

  const handleRefineClick = () => {
    if (conversationId) {
      router.push(`/ideation-queue/${conversationId}`);
    }
  };

  // Determine if research can be launched (need valid idea markdown)
  const canLaunchResearch =
    idea?.active_version?.idea_markdown && idea.active_version.title !== "Generating...";

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

  // No idea data for this conversation - likely still generating
  if (!idea) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center">
        <div className="mb-4 h-8 w-8 animate-spin rounded-full border-2 border-slate-600 border-t-emerald-500" />
        <h3 className="mb-1 text-sm font-medium text-slate-300">Generating idea...</h3>
        <p className="text-xs text-slate-500">
          The idea is being generated. It will appear here when ready.
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
        <h2 className="text-xl sm:text-2xl font-semibold text-white">
          {activeVersion?.title || "Untitled Idea"}
        </h2>

        {/* Metadata row - stacks on mobile */}
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:gap-6">
          {/* Created date and run count */}
          <div className="flex flex-wrap items-center gap-3 sm:gap-4">
            {activeVersion?.created_at && (
              <div className="text-sm">
                <span className="text-slate-500">Created: </span>
                <span className="text-slate-300">
                  {new Date(activeVersion.created_at).toLocaleString()}
                </span>
              </div>
            )}

            {runCount > 0 && (
              <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-500/15 px-3 py-1 text-xs font-medium text-emerald-400">
                <FlaskConical className="h-3 w-3" />
                {runCount} {runCount === 1 ? "run" : "runs"}
              </span>
            )}
          </div>

          {/* Action buttons - full width on mobile */}
          <div className="flex items-center gap-2 sm:ml-auto">
            <LaunchResearchButton conversationId={conversationId} disabled={!canLaunchResearch} />
            <Button
              onClick={handleRefineClick}
              variant="outline"
              size="sm"
              aria-label="Refine research idea"
            >
              <Pencil className="h-3 w-3 mr-1.5" />
              Refine further
            </Button>
          </div>
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
