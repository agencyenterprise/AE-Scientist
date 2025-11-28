import { useMemo } from "react";
import { ReactElement } from "react";
import type { IdeaVersion } from "@/types";
import { generateSectionDiffs, canCompareVersions, type SectionDiffs } from "../utils/diffUtils";

interface UseDiffGenerationProps {
  showDiffs: boolean;
  comparisonVersion: IdeaVersion | null;
  nextVersion: IdeaVersion | null;
}

interface UseDiffGenerationReturn {
  // Title diff (for header)
  titleDiffContent: ReactElement[] | null;
  // All section diffs
  sectionDiffs: SectionDiffs | null;
  // Can show diffs flag
  canShowDiffs: boolean;
}

export function useDiffGeneration({
  showDiffs,
  comparisonVersion,
  nextVersion,
}: UseDiffGenerationProps): UseDiffGenerationReturn {
  // Check if diffs can be shown
  const canShowDiffs = useMemo(() => {
    return showDiffs && canCompareVersions(comparisonVersion, nextVersion);
  }, [showDiffs, comparisonVersion, nextVersion]);

  // Generate all section diffs
  const sectionDiffs = useMemo((): SectionDiffs | null => {
    if (!canShowDiffs || !comparisonVersion || !nextVersion) {
      return null;
    }

    return generateSectionDiffs(comparisonVersion, nextVersion);
  }, [canShowDiffs, comparisonVersion, nextVersion]);

  // Extract title diff for backwards compatibility
  const titleDiffContent = sectionDiffs?.title ?? null;

  return {
    titleDiffContent,
    sectionDiffs,
    canShowDiffs,
  };
}
