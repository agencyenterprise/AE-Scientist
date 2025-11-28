import React from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import type { IdeaVersion } from "@/types";

interface VersionNavigationPanelProps {
  comparisonVersion: IdeaVersion;
  totalVersions: number;
  canNavigatePrevious: boolean;
  canNavigateNext: boolean;
  onPreviousVersion: () => void;
  onNextVersion: () => void;
  newVersionAnimation?: boolean;
}

export function VersionNavigationPanel({
  comparisonVersion,
  totalVersions,
  canNavigatePrevious,
  canNavigateNext,
  onPreviousVersion,
  onNextVersion,
  newVersionAnimation = false,
}: VersionNavigationPanelProps): React.JSX.Element {
  return (
    <div
      className={`inline-flex items-center gap-0.5 rounded-lg border border-border bg-card shadow-sm p-0.5 transition-all duration-500 ${
        newVersionAnimation ? "ring-1 ring-primary/30 shadow-md shadow-primary/10" : ""
      }`}
    >
      {/* Revisions Label */}
      <span className="px-2 py-1 text-xs font-medium text-muted-foreground uppercase tracking-wide">
        Revisions
      </span>

      {/* Previous Button */}
      <button
        onClick={onPreviousVersion}
        disabled={!canNavigatePrevious}
        aria-label="Go to previous version"
        aria-disabled={!canNavigatePrevious}
        className={`flex items-center justify-center w-7 h-7 rounded-md transition-all duration-150 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none ${
          !canNavigatePrevious
            ? "text-muted-foreground/40 cursor-not-allowed"
            : "text-muted-foreground hover:text-foreground hover:bg-muted active:scale-95"
        }`}
      >
        <ChevronLeft size={16} />
      </button>

      {/* Version Badge */}
      <div className="px-2.5 py-1 text-xs bg-muted rounded-md">
        <span className="font-mono font-medium text-foreground">
          v{comparisonVersion.version_number}
        </span>
        <span className="text-muted-foreground"> of {totalVersions}</span>
      </div>

      {/* Next Button */}
      <button
        onClick={onNextVersion}
        disabled={!canNavigateNext}
        aria-label="Go to next version"
        aria-disabled={!canNavigateNext}
        className={`flex items-center justify-center w-7 h-7 rounded-md transition-all duration-150 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none ${
          !canNavigateNext
            ? "text-muted-foreground/40 cursor-not-allowed"
            : "text-muted-foreground hover:text-foreground hover:bg-muted active:scale-95"
        }`}
      >
        <ChevronRight size={16} />
      </button>
    </div>
  );
}
