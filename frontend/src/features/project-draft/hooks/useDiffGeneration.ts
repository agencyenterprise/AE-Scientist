import { useMemo } from "react";
import { ReactElement } from "react";
import type { IdeaVersion } from "@/types";
import { generateTitleDiff, generateMarkdownDiff, canCompareVersions } from "../utils/diffUtils";

interface UseDiffGenerationProps {
  showDiffs: boolean;
  comparisonVersion: IdeaVersion | null;
  nextVersion: IdeaVersion | null;
}

interface UseDiffGenerationReturn {
  // Title diff (for header)
  titleDiffContent: ReactElement[] | null;
  // Markdown content diff
  markdownDiffContent: ReactElement[] | null;
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

  // Generate title diff
  const titleDiffContent = useMemo((): ReactElement[] | null => {
    if (!canShowDiffs || !comparisonVersion || !nextVersion) {
      return null;
    }

    return generateTitleDiff(comparisonVersion, nextVersion);
  }, [canShowDiffs, comparisonVersion, nextVersion]);

  // Generate markdown content diff
  const markdownDiffContent = useMemo((): ReactElement[] | null => {
    if (!canShowDiffs || !comparisonVersion || !nextVersion) {
      return null;
    }

    return generateMarkdownDiff(comparisonVersion, nextVersion);
  }, [canShowDiffs, comparisonVersion, nextVersion]);

  return {
    titleDiffContent,
    markdownDiffContent,
    canShowDiffs,
  };
}
