import type { IdeaVersion, Idea } from "@/types";

/**
 * Find a version by its version number
 */
export function findVersionByNumber(
  versions: IdeaVersion[],
  versionNumber: number
): IdeaVersion | null {
  return versions.find(v => v.version_number === versionNumber) || null;
}

/**
 * Get the comparison version based on selected version or default to previous
 */
export function getComparisonVersion(
  projectDraft: Idea | null,
  allVersions: IdeaVersion[],
  selectedVersionForComparison: number | null
): IdeaVersion | null {
  if (!projectDraft?.active_version || allVersions.length < 2) {
    return null;
  }

  // If a specific version is selected, use that
  if (selectedVersionForComparison) {
    return findVersionByNumber(allVersions, selectedVersionForComparison);
  }

  // Default to the previous version (version_number - 1)
  const currentVersionNumber = projectDraft.active_version.version_number;
  return findVersionByNumber(allVersions, currentVersionNumber - 1);
}

/**
 * Get the "next" version after the comparison version (the "to" version in the diff)
 */
export function getNextVersion(
  comparisonVersion: IdeaVersion | null,
  allVersions: IdeaVersion[]
): IdeaVersion | null {
  if (!comparisonVersion) {
    return null;
  }

  // Find the version that comes after the comparison version
  const nextVersionNumber = comparisonVersion.version_number + 1;
  return findVersionByNumber(allVersions, nextVersionNumber);
}

/**
 * Check if navigation to previous version is possible
 */
export function canNavigateToPrevious(comparisonVersion: IdeaVersion | null): boolean {
  return !!(comparisonVersion && comparisonVersion.version_number > 1);
}

/**
 * Check if navigation to next version is possible
 */
export function canNavigateToNext(
  comparisonVersion: IdeaVersion | null,
  projectDraft: Idea | null
): boolean {
  return !!(
    comparisonVersion &&
    projectDraft?.active_version &&
    comparisonVersion.version_number < projectDraft.active_version.version_number - 1
  );
}

/**
 * Get the previous version number for navigation
 */
export function getPreviousVersionNumber(comparisonVersion: IdeaVersion | null): number | null {
  if (!comparisonVersion) return null;

  const previousVersionNumber = comparisonVersion.version_number - 1;
  return previousVersionNumber >= 1 ? previousVersionNumber : null;
}

/**
 * Get the next version number for navigation
 */
export function getNextVersionNumber(
  comparisonVersion: IdeaVersion | null,
  projectDraft: Idea | null
): number | null {
  if (!comparisonVersion || !projectDraft?.active_version) return null;

  const nextVersionNumber = comparisonVersion.version_number + 1;
  return nextVersionNumber < projectDraft.active_version.version_number ? nextVersionNumber : null;
}

/**
 * Check if a project draft is currently being generated
 */
export function isIdeaGenerating(draft: Idea | null): boolean {
  return !!(
    draft?.active_version?.title === "Generating..." && draft?.active_version?.version_number === 1
  );
}

/**
 * Detect if a new version was created based on version numbers
 */
export function isNewVersionCreated(
  previousVersionNumber: number | undefined,
  newVersionNumber: number | undefined
): boolean {
  return !!(previousVersionNumber && newVersionNumber && newVersionNumber > previousVersionNumber);
}
