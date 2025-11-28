import type { Idea, IdeaVersion } from "@/types";
import { Undo2 } from "lucide-react";
import React from "react";
import { isIdeaGenerating } from "../utils/versionUtils";
import { VersionNavigationPanel } from "./VersionNavigationPanel";

interface ProjectDraftFooterProps {
  projectDraft: Idea;
  isEditing: boolean;
  showDiffs: boolean;
  comparisonVersion: IdeaVersion | null;
  nextVersion: IdeaVersion | null;
  allVersions: IdeaVersion[];
  canNavigatePrevious: boolean;
  canNavigateNext: boolean;
  newVersionAnimation: boolean;
  onPreviousVersion: () => void;
  onNextVersion: () => void;
  onRevertChanges: () => Promise<void>;
  onCreateProject: () => void;
}

export function ProjectDraftFooter({
  projectDraft,
  isEditing,
  showDiffs,
  comparisonVersion,
  nextVersion,
  allVersions,
  canNavigatePrevious,
  canNavigateNext,
  newVersionAnimation,
  onPreviousVersion,
  onNextVersion,
  onRevertChanges,
  onCreateProject,
}: ProjectDraftFooterProps): React.JSX.Element {
  const isGenerating = isIdeaGenerating(projectDraft);

  return (
    <>
      {/* Version Info and Diff Legend */}
      <div className="flex-shrink-0 py-2 text-xs text-muted-foreground flex items-center justify-between">
        <div>
          {showDiffs && comparisonVersion && nextVersion && !isEditing && !isGenerating
            ? `Changes from version ${comparisonVersion.version_number} to ${nextVersion.version_number}`
            : `Version ${projectDraft.active_version?.version_number || "?"}`}{" "}
          • {projectDraft.active_version?.is_manual_edit ? "Manual edit" : "AI generated"} •{" "}
          {projectDraft.active_version?.created_at
            ? new Date(projectDraft.active_version.created_at).toLocaleDateString()
            : "Unknown date"}
        </div>
        {showDiffs && comparisonVersion && nextVersion && !isEditing && !isGenerating && (
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

      {/* Footer with Navigation, Revert Button and Create Project Button */}
      <div className="flex-shrink-0 py-3 border-border flex items-center justify-between">
        {/* Version navigation and revert controls */}
        {showDiffs && comparisonVersion && nextVersion && !isEditing && !isGenerating && (
          <div className="flex items-center space-x-2">
            {/* Version navigation controls */}
            {allVersions.length > 2 && (
              <VersionNavigationPanel
                comparisonVersion={comparisonVersion}
                totalVersions={allVersions.length}
                canNavigatePrevious={canNavigatePrevious}
                canNavigateNext={canNavigateNext}
                onPreviousVersion={onPreviousVersion}
                onNextVersion={onNextVersion}
                newVersionAnimation={newVersionAnimation}
              />
            )}

            {/* Revert changes button */}
            <button
              onClick={onRevertChanges}
              className="flex items-center space-x-1 px-2 py-1 text-xs font-medium text-red-300 bg-red-500/10 hover:bg-red-500/20 rounded border border-red-500/30 transition-colors"
            >
              <Undo2 className="w-3 h-3" />
              <span>Revert changes</span>
            </button>
          </div>
        )}

        {/* Create Project button */}
        <button
          onClick={onCreateProject}
          disabled={isGenerating}
          className={`btn-primary-gradient w-full text-xs py-3 px-2 ${
            isGenerating ? "opacity-50 cursor-not-allowed" : ""
          } ${
            !showDiffs || !comparisonVersion || !nextVersion || isEditing || isGenerating
              ? "ml-auto"
              : ""
          }`}
        >
          <span>Launch Project</span>
        </button>
      </div>
    </>
  );
}
