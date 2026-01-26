import type { ReactElement } from "react";
import { diff_match_patch } from "diff-match-patch";
import type { IdeaVersion } from "@/types";

/**
 * Interface for diff result with React elements
 */
export interface DiffContent {
  elements: ReactElement[];
}

/**
 * Generate diff elements for a string comparison
 */
export function generateStringDiff(
  oldText: string,
  newText: string,
  keyPrefix: string = "diff"
): ReactElement[] {
  if (oldText === newText) {
    return [
      <span key={`${keyPrefix}-0`} className="text-foreground">
        {newText}
      </span>,
    ];
  }

  const dmp = new diff_match_patch();
  const diffs = dmp.diff_main(oldText, newText);
  dmp.diff_cleanupSemantic(diffs);

  return diffs.map((diff, index) => {
    const [operation, text] = diff;

    if (operation === 0) {
      // No change
      return (
        <span key={`${keyPrefix}-${index}`} className="text-foreground">
          {text}
        </span>
      );
    } else if (operation === -1) {
      // Deletion
      return (
        <span key={`${keyPrefix}-${index}`} className="bg-red-500/20 text-red-400 px-0.5 rounded">
          <span className="line-through">{text}</span>
        </span>
      );
    } else {
      // Addition
      return (
        <span
          key={`${keyPrefix}-${index}`}
          className="bg-green-500/20 text-green-400 px-0.5 rounded"
        >
          <span className="font-medium">{text}</span>
        </span>
      );
    }
  });
}

/**
 * Generate diff content showing entire text as deleted
 */
export function generateDeletedDiff(text: string, keyPrefix: string = "del"): ReactElement[] {
  return [
    <span key={`${keyPrefix}-0`} className="bg-red-500/20 text-red-400 px-0.5 rounded">
      <span className="line-through">{text}</span>
    </span>,
  ];
}

/**
 * Generate diff content showing entire text as added
 */
export function generateAddedDiff(text: string, keyPrefix: string = "add"): ReactElement[] {
  return [
    <span key={`${keyPrefix}-0`} className="bg-green-500/20 text-green-400 px-0.5 rounded">
      <span className="font-medium">{text}</span>
    </span>,
  ];
}

/**
 * Generate diff content for title comparison between two versions
 */
export function generateTitleDiff(
  fromVersion: IdeaVersion,
  toVersion: IdeaVersion
): ReactElement[] {
  const oldTitle = fromVersion.title;
  const newTitle = toVersion.title;
  return generateStringDiff(oldTitle, newTitle, "title");
}

/**
 * Generate diff content for markdown comparison between two versions
 */
export function generateMarkdownDiff(
  fromVersion: IdeaVersion,
  toVersion: IdeaVersion
): ReactElement[] {
  const oldMarkdown = fromVersion.idea_markdown || "";
  const newMarkdown = toVersion.idea_markdown || "";
  return generateStringDiff(oldMarkdown, newMarkdown, "markdown");
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
