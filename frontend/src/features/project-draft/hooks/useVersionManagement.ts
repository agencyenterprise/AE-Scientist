import { useState, useCallback, useMemo } from "react";
import type { Idea, IdeaVersion, IdeaVersionsResponse } from "@/types";
import { config } from "@/shared/lib/config";
import {
  getComparisonVersion,
  getNextVersion,
  canNavigateToPrevious,
  canNavigateToNext,
  getPreviousVersionNumber,
  getNextVersionNumber,
} from "../utils/versionUtils";

interface UseVersionManagementProps {
  conversationId: string;
  projectDraft: Idea | null;
}

interface UseVersionManagementReturn {
  showDiffs: boolean;
  setShowDiffs: (show: boolean) => void;
  allVersions: IdeaVersion[];
  selectedVersionForComparison: number | null;
  setSelectedVersionForComparison: (version: number | null) => void;
  comparisonVersion: IdeaVersion | null;
  nextVersion: IdeaVersion | null;
  canNavigatePrevious: boolean;
  canNavigateNext: boolean;
  handlePreviousVersion: () => void;
  handleNextVersion: () => void;
  loadVersions: () => Promise<void>;
}

export function useVersionManagement({
  conversationId,
  projectDraft,
}: UseVersionManagementProps): UseVersionManagementReturn {
  const [showDiffs, setShowDiffs] = useState(true);
  const [allVersions, setAllVersions] = useState<IdeaVersion[]>([]);
  const [selectedVersionForComparison, setSelectedVersionForComparison] = useState<number | null>(
    null
  );

  // Get comparison version for diff (either selected or default to previous)
  const comparisonVersion = useMemo((): IdeaVersion | null => {
    return getComparisonVersion(projectDraft, allVersions, selectedVersionForComparison);
  }, [projectDraft, allVersions, selectedVersionForComparison]);

  // Get the "next" version after the comparison version (the "to" version in the diff)
  const nextVersion = useMemo((): IdeaVersion | null => {
    return getNextVersion(comparisonVersion, allVersions);
  }, [comparisonVersion, allVersions]);

  // Check if navigation is available
  const canNavigatePrevious = canNavigateToPrevious(comparisonVersion);
  const canNavigateNext = canNavigateToNext(comparisonVersion, projectDraft);

  // Navigation functions for version comparison
  const handlePreviousVersion = (): void => {
    const previousVersionNumber = getPreviousVersionNumber(comparisonVersion);
    if (previousVersionNumber !== null) {
      setSelectedVersionForComparison(previousVersionNumber);
    }
  };

  const handleNextVersion = (): void => {
    const nextVersionNumber = getNextVersionNumber(comparisonVersion, projectDraft);
    if (nextVersionNumber !== null) {
      setSelectedVersionForComparison(nextVersionNumber);
    }
  };

  // Load idea versions
  const loadVersions = useCallback(async (): Promise<void> => {
    try {
      const response = await fetch(
        `${config.apiUrl}/conversations/${conversationId}/idea/versions`,
        {
          credentials: "include",
        }
      );
      if (response.ok) {
        const result: IdeaVersionsResponse = await response.json();
        setAllVersions(result.versions);
      }
    } catch (error) {
      // eslint-disable-next-line no-console
      console.error("Failed to load versions:", error);
    }
  }, [conversationId]);

  // Wrapper function that combines state updates to avoid cascading effects
  const setShowDiffsWithReset = useCallback((show: boolean) => {
    setShowDiffs(show);
    if (!show) {
      setSelectedVersionForComparison(null);
    }
  }, []);

  return {
    showDiffs,
    setShowDiffs: setShowDiffsWithReset,
    allVersions,
    selectedVersionForComparison,
    setSelectedVersionForComparison,
    comparisonVersion,
    nextVersion,
    canNavigatePrevious,
    canNavigateNext,
    handlePreviousVersion,
    handleNextVersion,
    loadVersions,
  };
}
