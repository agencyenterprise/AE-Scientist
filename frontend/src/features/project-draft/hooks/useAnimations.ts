import { useState } from "react";
import type { Idea } from "@/types";
import { isNewVersionCreated } from "../utils/versionUtils";

interface UseAnimationsReturn {
  updateAnimation: boolean;
  newVersionAnimation: boolean;
  triggerUpdateAnimation: () => void;
  handleExternalUpdate: (
    externalUpdate: Idea | null,
    currentIdea: Idea | null,
    setIdea: (draft: Idea) => void,
    setSelectedVersionForComparison: (version: number | null) => void,
    setShowDiffs: (show: boolean) => void,
    loadVersions: () => Promise<void>
  ) => void;
}

export function useAnimations(): UseAnimationsReturn {
  const [updateAnimation, setUpdateAnimation] = useState(false);
  const [newVersionAnimation, setNewVersionAnimation] = useState(false);

  const triggerUpdateAnimation = (): void => {
    setUpdateAnimation(true);
    setTimeout(() => setUpdateAnimation(false), 2000);
  };

  const handleExternalUpdate = async (
    externalUpdate: Idea | null,
    currentIdea: Idea | null,
    setIdea: (draft: Idea) => void,
    setSelectedVersionForComparison: (version: number | null) => void,
    setShowDiffs: (show: boolean) => void,
    loadVersions: () => Promise<void>
  ): Promise<void> => {
    if (!externalUpdate) return;

    // Store the previous version number before updating
    const previousVersionNumber = currentIdea?.active_version?.version_number;

    setIdea(externalUpdate);
    triggerUpdateAnimation();

    // Check if a new version was created
    const newVersionNumber = externalUpdate.active_version?.version_number;
    if (isNewVersionCreated(previousVersionNumber, newVersionNumber)) {
      // New version was created! Set comparison to show what changed
      setSelectedVersionForComparison(previousVersionNumber || null);

      // Trigger new version animation
      setNewVersionAnimation(true);
      setTimeout(() => setNewVersionAnimation(false), 2000);

      // Ensure we're in diff mode to show the changes
      setShowDiffs(true);
    }

    // Reload versions after external update
    await loadVersions();
  };

  return {
    updateAnimation,
    newVersionAnimation,
    triggerUpdateAnimation,
    handleExternalUpdate,
  };
}
