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
      className={`border border-gray-300 rounded bg-white flex items-center text-xs transition-all duration-500 ${
        newVersionAnimation ? "ring-2 ring-green-400 shadow-lg scale-105" : ""
      }`}
    >
      {/* Version Label - Left side */}
      <div className="px-1.5 py-1 border-r border-gray-200 bg-gray-50">
        <span className="font-medium text-gray-600 uppercase tracking-wide text-xs">Version</span>
      </div>

      {/* Previous Button */}
      <button
        onClick={onPreviousVersion}
        disabled={!canNavigatePrevious}
        className={`flex items-center px-1.5 py-1 font-medium border-r border-gray-200 ${
          !canNavigatePrevious
            ? "text-gray-300 cursor-not-allowed bg-gray-50"
            : "text-gray-700 hover:bg-gray-50"
        }`}
        title="Previous version"
      >
        ⬅️
      </button>

      {/* Version Number */}
      <div
        className={`px-1.5 py-1 border-r border-gray-200 transition-all duration-500 ${
          newVersionAnimation ? "bg-green-200 ring-2 ring-green-400" : "bg-gray-50"
        }`}
      >
        <span
          className={`font-medium text-xs transition-colors duration-500 ${
            newVersionAnimation ? "text-green-800" : "text-gray-800"
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
            ? "text-gray-300 cursor-not-allowed bg-gray-50"
            : "text-gray-700 hover:bg-gray-50"
        }`}
        title="Next version"
      >
        ➡️
      </button>
    </div>
  );
}
