import type { Idea, IdeaVersion } from "@/types";
import React from "react";
import { isIdeaGenerating } from "../utils/versionUtils";
import { useConversationContext } from "@/features/conversation/context/ConversationContext";

import { cn } from "@/shared/lib/utils";

interface ProjectDraftFooterProps {
  projectDraft: Idea;
  showDiffs: boolean;
  comparisonVersion: IdeaVersion | null;
  nextVersion: IdeaVersion | null;
  onCreateProject: () => void;
}

export function ProjectDraftFooter({
  projectDraft,
  showDiffs,
  comparisonVersion,
  nextVersion,
  onCreateProject,
}: ProjectDraftFooterProps): React.JSX.Element {
  const { isStreaming, isPollingEmptyMessage } = useConversationContext();
  const isGenerating = isIdeaGenerating(projectDraft);

  // Check if user is viewing a historical version (not the current active version)
  const isViewingHistoricalVersion = Boolean(
    showDiffs &&
      nextVersion &&
      projectDraft.active_version &&
      nextVersion.version_number !== projectDraft.active_version.version_number
  );

  // Disable when: generating idea, streaming response, polling for response (after refresh), or viewing old version
  const isAwaitingResponse = isStreaming || isPollingEmptyMessage;
  const isDisabled = isGenerating || isAwaitingResponse || isViewingHistoricalVersion;

  return (
    <>
      {/* Version Info and Diff Legend */}
      <div className="flex-shrink-0 py-2 text-[10px] sm:text-xs text-muted-foreground flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
        <div>
          {showDiffs && comparisonVersion && nextVersion && !isGenerating
            ? `Changes from v${comparisonVersion.version_number} to v${nextVersion.version_number}`
            : `Version ${projectDraft.active_version?.version_number || "?"}`}{" "}
          • {projectDraft.active_version?.is_manual_edit ? "Manual" : "AI"} •{" "}
          {projectDraft.active_version?.created_at
            ? new Date(projectDraft.active_version.created_at).toLocaleDateString()
            : "Unknown date"}
        </div>
        {showDiffs && comparisonVersion && nextVersion && !isGenerating && (
          <div className="hidden sm:block">
            <span className="inline-flex items-center">
              <span className="w-3 h-3 bg-red-500/20 border border-red-500/30 rounded mr-2"></span>
              Removed
            </span>
            <span className="inline-flex items-center ml-4">
              <span className="w-3 h-3 bg-green-500/20 border border-green-500/30 rounded mr-2"></span>
              Added
            </span>
          </div>
        )}
      </div>

      {/* Footer with Create Project Button */}
      <div className="flex-shrink-0 py-3 border-border">
        <button
          onClick={onCreateProject}
          disabled={isDisabled}
          title={
            isViewingHistoricalVersion
              ? "Navigate to the latest version or revert to this version before launching research"
              : undefined
          }
          className={cn("btn-primary-gradient w-full text-xs py-3 px-2", {
            "opacity-50 cursor-not-allowed": isDisabled,
          })}
        >
          <span>Launch Research</span>
        </button>
      </div>
    </>
  );
}
