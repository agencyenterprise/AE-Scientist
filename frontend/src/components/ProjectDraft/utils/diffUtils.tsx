import React, { ReactElement } from "react";
import { diff_match_patch } from "diff-match-patch";
import type { IdeaVersion } from "@/types";

/**
 * Interface for diff result with React elements
 */
export interface DiffContent {
  elements: ReactElement[];
}

/**
 * Generate diff content for title comparison between two versions
 */
export function generateTitleDiff(
  fromVersion: IdeaVersion,
  toVersion: IdeaVersion
): ReactElement[] {
  const dmp = new diff_match_patch();
  const diffs = dmp.diff_main(fromVersion.title, toVersion.title);
  dmp.diff_cleanupSemantic(diffs);

  return diffs.map((diff, index) => {
    const [operation, text] = diff;

    if (operation === 0) {
      // No change
      return (
        <span key={index} className="text-gray-900">
          {text}
        </span>
      );
    } else if (operation === -1) {
      // Deletion
      return (
        <span key={index} className="bg-red-100 text-red-800 px-1 rounded">
          <span className="line-through">{text}</span>
        </span>
      );
    } else {
      // Addition
      return (
        <span key={index} className="bg-green-100 text-green-800 px-1 rounded">
          <span className="font-medium">{text}</span>
        </span>
      );
    }
  });
}

/**
 * Generate diff content for description comparison between two versions
 */
export function generateDescriptionDiff(
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  _fromVersion: IdeaVersion,
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  _toVersion: IdeaVersion
): ReactElement[] {
  // Diff functionality not supported for complex idea structure
  // (ideas now have multiple fields instead of a single description)
  return [];
}

/**
 * Check if two versions can be compared for diffs
 */
export function canCompareVersions(
  fromVersion: IdeaVersion | null,
  toVersion: IdeaVersion | null
): boolean {
  return !!(fromVersion && toVersion && fromVersion.version_id !== toVersion.version_id);
}
