import React, { ReactElement, useState, useRef, useEffect } from "react";
import type { Idea, IdeaVersion } from "@/types";
import { isIdeaGenerating } from "../utils/versionUtils";
import { GitCompare, Undo2, Check, X, Loader2 } from "lucide-react";
import { VersionNavigationPanel } from "./VersionNavigationPanel";

interface ProjectDraftHeaderProps {
  projectDraft: Idea;
  showDiffs: boolean;
  setShowDiffs: (show: boolean) => void;
  comparisonVersion: IdeaVersion | null;
  nextVersion: IdeaVersion | null;
  titleDiffContent: ReactElement[] | null;
  onTitleSave: (newTitle: string) => Promise<void>;
  isTitleSaving: boolean;
  // Version navigation props
  allVersions: IdeaVersion[];
  canNavigatePrevious: boolean;
  canNavigateNext: boolean;
  newVersionAnimation: boolean;
  onPreviousVersion: () => void;
  onNextVersion: () => void;
  onRevertChanges: () => Promise<void>;
}

export function ProjectDraftHeader({
  projectDraft,
  showDiffs,
  setShowDiffs,
  comparisonVersion,
  nextVersion,
  titleDiffContent,
  onTitleSave,
  isTitleSaving,
  allVersions,
  canNavigatePrevious,
  canNavigateNext,
  newVersionAnimation,
  onPreviousVersion,
  onNextVersion,
  onRevertChanges,
}: ProjectDraftHeaderProps): React.JSX.Element {
  const isGenerating = isIdeaGenerating(projectDraft);
  const hasMultipleVersions = allVersions.length > 1;
  const canRevert = comparisonVersion && nextVersion && !isGenerating;

  // Inline title editing state
  const [isEditingTitle, setIsEditingTitle] = useState(false);
  const [editValue, setEditValue] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  const currentTitle = projectDraft.active_version?.title || "Research Idea";

  // Focus input when editing starts
  useEffect(() => {
    if (isEditingTitle && inputRef.current) {
      inputRef.current.focus();
      inputRef.current.select();
    }
  }, [isEditingTitle]);

  const handleStartEdit = (): void => {
    setEditValue(currentTitle);
    setIsEditingTitle(true);
  };

  const handleCancelEdit = (): void => {
    setIsEditingTitle(false);
    setEditValue("");
  };

  const handleSaveEdit = async (): Promise<void> => {
    const trimmed = editValue.trim();
    if (!trimmed || trimmed === currentTitle) {
      handleCancelEdit();
      return;
    }
    await onTitleSave(trimmed);
    setIsEditingTitle(false);
    setEditValue("");
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>): void => {
    if (e.key === "Enter") {
      e.preventDefault();
      handleSaveEdit();
    } else if (e.key === "Escape") {
      handleCancelEdit();
    }
  };

  return (
    <div className="flex-shrink-0 pt-1 pb-1">
      {/* Version controls */}
      <div className="flex items-center justify-end gap-1.5 sm:gap-2 flex-wrap mb-1">
        {/* Show diffs toggle */}
        {!isGenerating && comparisonVersion && nextVersion && (
          <button
            onClick={() => setShowDiffs(!showDiffs)}
            className={`flex items-center gap-1.5 px-2 py-1 text-xs font-medium rounded transition-colors ${
              showDiffs
                ? "text-primary bg-primary/10"
                : "text-muted-foreground hover:text-foreground hover:bg-muted"
            }`}
            title={showDiffs ? "Hide changes" : "Show changes"}
            aria-label={showDiffs ? "Hide changes" : "Show changes"}
          >
            <GitCompare className="w-3.5 h-3.5" />
            <span>{showDiffs ? "Hide changes" : "Show changes"}</span>
          </button>
        )}

        {/* Version navigation (only when diffs enabled) */}
        {showDiffs && !isGenerating && hasMultipleVersions && comparisonVersion && (
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

        {/* Revert button (only when diffs enabled) */}
        {showDiffs && canRevert && (
          <button
            onClick={onRevertChanges}
            className="p-1.5 text-red-400/70 hover:text-red-400 hover:bg-red-500/10 rounded transition-colors"
            title="Revert to this version"
            aria-label="Revert changes"
          >
            <Undo2 className="w-3.5 h-3.5" />
          </button>
        )}
      </div>

      {/* Title with inline editing */}
      <div className="flex items-center gap-2">
        {isEditingTitle ? (
          <div className="flex-1 flex items-center gap-2">
            <input
              ref={inputRef}
              type="text"
              value={editValue}
              onChange={e => setEditValue(e.target.value)}
              onKeyDown={handleKeyDown}
              onBlur={handleCancelEdit}
              disabled={isTitleSaving}
              className="flex-1 text-base font-semibold bg-slate-800 border border-slate-600 rounded px-2 py-1 text-foreground focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent"
            />
            <button
              onMouseDown={e => e.preventDefault()}
              onClick={handleSaveEdit}
              disabled={isTitleSaving}
              className="p-1 text-emerald-400 hover:text-emerald-300 hover:bg-emerald-500/10 rounded transition-colors"
              aria-label="Save title"
            >
              {isTitleSaving ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Check className="w-4 h-4" />
              )}
            </button>
            <button
              onMouseDown={e => e.preventDefault()}
              onClick={handleCancelEdit}
              disabled={isTitleSaving}
              className="p-1 text-muted-foreground hover:text-foreground hover:bg-muted rounded transition-colors"
              aria-label="Cancel editing"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        ) : (
          <div
            className="flex-1 group cursor-pointer"
            onClick={!isGenerating ? handleStartEdit : undefined}
          >
            <h3
              className={`text-base font-semibold ${
                isGenerating ? "text-primary" : "text-foreground group-hover:text-primary"
              } transition-colors`}
              title={!isGenerating ? "Click to edit title" : undefined}
            >
              {showDiffs && comparisonVersion && nextVersion && titleDiffContent
                ? titleDiffContent
                : currentTitle}
            </h3>
          </div>
        )}
      </div>
    </div>
  );
}
