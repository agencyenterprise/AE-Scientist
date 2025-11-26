import React from "react";
import type { IdeaVersion } from "@/types";

interface VersionNavigationPanelProps {
  comparisonVersion: IdeaVersion;
  canNavigatePrevious: boolean;
  canNavigateNext: boolean;
  onPreviousVersion: () => void;
  onNextVersion: () => void;
  newVersionAnimation?: boolean;
}

export function VersionNavigationPanel({
  comparisonVersion,
  canNavigatePrevious,
  canNavigateNext,
  onPreviousVersion,
  onNextVersion,
  newVersionAnimation = false,
}: VersionNavigationPanelProps): React.JSX.Element {
  return (
    <div
      className={`border border-border rounded bg-card flex items-center text-xs transition-all duration-500 ${
        newVersionAnimation ? "ring-2 ring-green-500 shadow-lg scale-105" : ""
      }`}
    >
      {/* Version Label - Left side */}
      <div className="px-1.5 py-1 border-r border-border bg-muted">
        <span className="font-medium text-muted-foreground uppercase tracking-wide text-xs">Version</span>
      </div>

      {/* Previous Button */}
      <button
        onClick={onPreviousVersion}
        disabled={!canNavigatePrevious}
        className={`flex items-center px-1.5 py-1 font-medium border-r border-border ${
          !canNavigatePrevious
            ? "text-muted-foreground/50 cursor-not-allowed bg-muted"
            : "text-foreground hover:bg-muted"
        }`}
        title="Previous version"
      >
        ⬅️
      </button>

      {/* Version Number */}
      <div
        className={`px-1.5 py-1 border-r border-border transition-all duration-500 ${
          newVersionAnimation ? "bg-green-500/20 ring-2 ring-green-500" : "bg-muted"
        }`}
      >
        <span
          className={`font-medium text-xs transition-colors duration-500 ${
            newVersionAnimation ? "text-green-400" : "text-foreground"
          }`}
        >
          v{comparisonVersion.version_number}
        </span>
      </div>

      {/* Next Button */}
      <button
        onClick={onNextVersion}
        disabled={!canNavigateNext}
        className={`flex items-center px-1.5 py-1 font-medium ${
          !canNavigateNext
            ? "text-muted-foreground/50 cursor-not-allowed bg-muted"
            : "text-foreground hover:bg-muted"
        }`}
        title="Next version"
      >
        ➡️
      </button>
    </div>
  );
}
