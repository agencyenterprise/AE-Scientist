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
      className={`inline-flex items-center gap-0.5 rounded border border-border/50 bg-muted/30 p-0.5 transition-all duration-500 ${
        newVersionAnimation ? "ring-1 ring-primary/20 shadow-sm shadow-primary/10" : ""
      }`}
    >
      {/* Previous Button */}
      <button
        onClick={onPreviousVersion}
        disabled={!canNavigatePrevious}
        aria-label="Go to previous version"
        aria-disabled={!canNavigatePrevious}
        className={`flex items-center justify-center w-5 h-5 rounded transition-all duration-150 focus-visible:ring-1 focus-visible:ring-ring focus-visible:outline-none ${
          !canNavigatePrevious
            ? "text-muted-foreground/30 cursor-not-allowed"
            : "text-muted-foreground/70 hover:text-foreground hover:bg-muted active:scale-95"
        }`}
      >
        <ChevronLeft size={14} />
      </button>

      {/* Version Badge */}
      <div className="px-1.5 py-0.5 text-[10px] text-muted-foreground">
        <span className="font-mono">v{comparisonVersion.version_number}</span>
        <span className="text-muted-foreground/70">/{totalVersions}</span>
      </div>

      {/* Next Button */}
      <button
        onClick={onNextVersion}
        disabled={!canNavigateNext}
        aria-label="Go to next version"
        aria-disabled={!canNavigateNext}
        className={`flex items-center justify-center w-5 h-5 rounded transition-all duration-150 focus-visible:ring-1 focus-visible:ring-ring focus-visible:outline-none ${
          !canNavigateNext
            ? "text-muted-foreground/30 cursor-not-allowed"
            : "text-muted-foreground/70 hover:text-foreground hover:bg-muted active:scale-95"
        }`}
      >
        <ChevronRight size={14} />
      </button>
    </div>
  );
}
