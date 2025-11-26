import React from "react";
import type { Idea, IdeaVersion } from "@/types";
import { VersionNavigationPanel } from "./VersionNavigationPanel";
import { isIdeaGenerating } from "../utils/versionUtils";

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
      <div className="flex-shrink-0 py-2 text-xs text-gray-500 flex items-center justify-between">
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
              <span className="w-3 h-3 bg-red-100 border border-red-200 rounded mr-2"></span>
              Removed
            </span>
            <span className="inline-flex items-center ml-4">
              <span className="w-3 h-3 bg-green-100 border border-green-200 rounded mr-2"></span>
              Added
            </span>
          </div>
        )}
      </div>

      {/* Footer with Navigation, Revert Button and Create Project Button */}
      <div className="flex-shrink-0 py-3 border-gray-200 flex items-center justify-between">
        {/* Version navigation and revert controls */}
        {showDiffs && comparisonVersion && nextVersion && !isEditing && !isGenerating && (
          <div className="flex items-center space-x-2">
            {/* Version navigation controls */}
            {allVersions.length > 2 && (
              <VersionNavigationPanel
                comparisonVersion={comparisonVersion}
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
              className="flex items-center space-x-1 px-2 py-1 text-xs font-medium text-red-600 hover:text-red-800 hover:bg-red-50 rounded border border-red-200 transition-colors"
            >
              <span>↶</span>
              <span>Revert changes</span>
            </button>
          </div>
        )}

        {/* Create Project button */}
        <button
          onClick={onCreateProject}
          disabled={isGenerating}
          className={`flex items-center space-x-1 px-2 py-1 text-xs font-medium rounded transition-colors ${
            isGenerating
              ? "bg-gray-400 text-gray-600 cursor-not-allowed"
              : "bg-green-600 text-white hover:bg-green-700"
          } ${
            !showDiffs || !comparisonVersion || !nextVersion || isEditing || isGenerating
              ? "ml-auto"
              : ""
          }`}
        >
          <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          <span>Create Project</span>
        </button>
      </div>
    </>
  );
}
