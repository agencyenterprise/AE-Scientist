import type { Idea, IdeaVersion } from "@/types";
import React from "react";
import { isIdeaGenerating } from "../utils/versionUtils";

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
  const isGenerating = isIdeaGenerating(projectDraft);

  return (
    <>
      {/* Version Info and Diff Legend */}
      <div className="flex-shrink-0 py-2 text-xs text-muted-foreground flex items-center justify-between">
        <div>
          {showDiffs && comparisonVersion && nextVersion && !isGenerating
            ? `Changes from version ${comparisonVersion.version_number} to ${nextVersion.version_number}`
            : `Version ${projectDraft.active_version?.version_number || "?"}`}{" "}
          • {projectDraft.active_version?.is_manual_edit ? "Manual edit" : "AI generated"} •{" "}
          {projectDraft.active_version?.created_at
            ? new Date(projectDraft.active_version.created_at).toLocaleDateString()
            : "Unknown date"}
        </div>
        {showDiffs && comparisonVersion && nextVersion && !isGenerating && (
          <div>
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
          disabled={isGenerating}
          className={cn("btn-primary-gradient w-full text-xs py-3 px-2", {
            "opacity-50 cursor-not-allowed": isGenerating,
          })}
        >
          <span>Launch Project</span>
        </button>
      </div>
    </>
  );
}
