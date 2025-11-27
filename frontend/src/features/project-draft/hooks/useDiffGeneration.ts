import { useMemo } from "react";
import { ReactElement } from "react";
import type { IdeaVersion } from "@/types";
import { generateTitleDiff, generateDescriptionDiff, canCompareVersions } from "../utils/diffUtils";

interface UseDiffGenerationProps {
  showDiffs: boolean;
  comparisonVersion: IdeaVersion | null;
  nextVersion: IdeaVersion | null;
}

interface UseDiffGenerationReturn {
  titleDiffContent: ReactElement[] | null;
  descriptionDiffContent: ReactElement[] | null;
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

  // Generate diff content for title
  const titleDiffContent = useMemo((): ReactElement[] | null => {
    if (!canShowDiffs || !comparisonVersion || !nextVersion) {
      return null;
    }

    return generateTitleDiff(comparisonVersion, nextVersion);
  }, [canShowDiffs, comparisonVersion, nextVersion]);

  // Generate diff content for description
  const descriptionDiffContent = useMemo((): ReactElement[] | null => {
    if (!canShowDiffs || !comparisonVersion || !nextVersion) {
      return null;
    }

    return generateDescriptionDiff(comparisonVersion, nextVersion);
  }, [canShowDiffs, comparisonVersion, nextVersion]);

  return {
    titleDiffContent,
    descriptionDiffContent,
    canShowDiffs,
  };
}
