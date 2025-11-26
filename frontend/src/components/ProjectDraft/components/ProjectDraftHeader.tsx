import React, { ReactElement } from "react";
import type { Idea, IdeaVersion } from "@/types";
import { isIdeaGenerating } from "../utils/versionUtils";

interface ProjectDraftHeaderProps {
  projectDraft: Idea;
  isEditing: boolean;
  editTitle: string;
  setEditTitle: (title: string) => void;
  showDiffs: boolean;
  setShowDiffs: (show: boolean) => void;
  comparisonVersion: IdeaVersion | null;
  nextVersion: IdeaVersion | null;
  titleDiffContent: ReactElement[] | null;
  onEdit: () => void;
  onKeyDown: (event: React.KeyboardEvent, action: () => void) => void;
  onSave: () => Promise<void>;
  onCancelEdit: () => void;
}

export function ProjectDraftHeader({
  projectDraft,
  isEditing,
  editTitle,
  setEditTitle,
  showDiffs,
  setShowDiffs,
  comparisonVersion,
  nextVersion,
  titleDiffContent,
  onEdit,
  onKeyDown,
  onSave,
  onCancelEdit,
}: ProjectDraftHeaderProps): React.JSX.Element {
  const isGenerating = isIdeaGenerating(projectDraft);

  return (
    <div className="flex-shrink-0 py-4">
      <div className="flex items-center justify-between mb-2">
        <label className="text-sm font-medium text-gray-700">Title</label>
        <div className="flex items-center space-x-2">
          {/* Show diffs toggle (hidden when no comparison available) */}
          {!isEditing && !isGenerating && comparisonVersion && nextVersion && (
            <button
              onClick={() => setShowDiffs(!showDiffs)}
              disabled={!comparisonVersion || !nextVersion}
              className={`relative flex items-center justify-center px-2 py-1 text-xs font-medium rounded border transition-colors w-32 ${
                !comparisonVersion || !nextVersion
                  ? "text-gray-400 bg-gray-100 border-gray-200 cursor-not-allowed"
                  : "text-gray-600 bg-gray-50 border-gray-200 hover:text-gray-800 hover:bg-gray-100"
              }`}
              title={
                !comparisonVersion || !nextVersion
                  ? "No version comparison available"
                  : showDiffs
                    ? "Show current"
                    : "Show diffs"
              }
            >
              <span className="absolute left-2">📄</span>
              <span className="pl-2">{showDiffs ? "Show current" : "Show diffs"}</span>
            </button>
          )}

          {/* Edit button */}
          {!isEditing && !isGenerating && (
            <button
              onClick={onEdit}
              disabled={
                !!(
                  showDiffs &&
                  nextVersion &&
                  projectDraft?.active_version &&
                  nextVersion.version_number !== projectDraft.active_version.version_number
                )
              }
              className={`flex items-center space-x-1 px-2 py-1 text-xs font-medium rounded border transition-colors ${
                showDiffs &&
                nextVersion &&
                projectDraft?.active_version &&
                nextVersion.version_number !== projectDraft.active_version.version_number
                  ? "text-gray-400 bg-gray-100 border-gray-200 cursor-not-allowed"
                  : "text-[var(--primary-700)] hover:bg-[var(--muted)] border-[var(--border)]"
              }`}
              title={
                showDiffs &&
                nextVersion &&
                projectDraft?.active_version &&
                nextVersion.version_number !== projectDraft.active_version.version_number
                  ? "Cannot edit when viewing older version comparison"
                  : "Edit idea"
              }
            >
              <span>✏️</span>
              <span>Edit</span>
            </button>
          )}
        </div>
      </div>

      {isEditing ? (
        <div>
          <input
            type="text"
            value={editTitle}
            onChange={e => setEditTitle(e.target.value)}
            onKeyDown={e => onKeyDown(e, onSave)}
            className="w-full px-3 py-2 text-base font-semibold border border-[var(--border)] rounded-md focus:outline-none focus:ring-2 focus:ring-[var(--ring)] focus:border-transparent bg-[var(--surface)] text-[var(--foreground)]"
            placeholder="Enter idea title..."
            autoFocus
          />
          <div className="flex justify-end space-x-2 mt-2">
            <button
              onClick={onCancelEdit}
              className="px-3 py-1 text-xs text-gray-600 hover:text-gray-800 hover:bg-gray-100 rounded border border-gray-200 transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={onSave}
              className="px-3 py-1 text-xs text-[var(--primary-foreground)] bg-[var(--primary)] hover:bg-[var(--primary-hover)] rounded transition-colors"
            >
              Save
            </button>
          </div>
        </div>
      ) : (
        <div className="flex items-center justify-between">
          <div className="flex-1">
            <h3
              className={`text-base font-semibold ${
                isGenerating ? "text-blue-900" : "text-gray-900"
              }`}
            >
              {showDiffs && comparisonVersion && nextVersion && titleDiffContent
                ? titleDiffContent
                : projectDraft.active_version?.title || ""}
            </h3>
          </div>
        </div>
      )}
    </div>
  );
}
