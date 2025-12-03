"use client";

import { useState, useEffect, useCallback } from "react";
import type { ConversationDetail, Idea, IdeaGetResponse } from "@/types";
import { apiFetch } from "@/shared/lib/api-client";
import { constants } from "@/shared/lib/config";
import { isIdeaGenerating } from "../utils/versionUtils";

/**
 * Options for the project draft data hook.
 */
export interface UseProjectDraftDataOptions {
  /** The conversation to load draft data for */
  conversation: ConversationDetail;
}

/**
 * Return type for the project draft data hook.
 */
export interface UseProjectDraftDataReturn {
  /** The project draft data */
  projectDraft: Idea | null;
  /** Set the project draft data */
  setProjectDraft: (draft: Idea) => void;
  /** Whether the initial data is loading */
  isLoading: boolean;
  /** Whether an update is in progress */
  isUpdating: boolean;
  /** Update the project draft with new data */
  updateProjectDraft: (ideaData: {
    title: string;
    short_hypothesis: string;
    related_work: string;
    abstract: string;
    experiments: string[];
    expected_outcome: string;
    risk_factors_and_limitations: string[];
  }) => Promise<void>;
}

/**
 * Hook for loading and managing project draft data.
 *
 * Extracted from useProjectDraftState to follow Single Responsibility Principle.
 * Handles:
 * - Initial data loading
 * - Polling during idea generation
 * - Updating project draft data
 *
 * @example
 * ```typescript
 * const { projectDraft, isLoading, updateProjectDraft } = useProjectDraftData({
 *   conversation,
 * });
 *
 * const handleSave = async (ideaData) => {
 *   await updateProjectDraft(ideaData);
 * };
 * ```
 */
export function useProjectDraftData({
  conversation,
}: UseProjectDraftDataOptions): UseProjectDraftDataReturn {
  const [projectDraft, setProjectDraft] = useState<Idea | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isUpdating, setIsUpdating] = useState(false);

  const updateProjectDraft = useCallback(
    async (ideaData: {
      title: string;
      short_hypothesis: string;
      related_work: string;
      abstract: string;
      experiments: string[];
      expected_outcome: string;
      risk_factors_and_limitations: string[];
    }): Promise<void> => {
      setIsUpdating(true);
      try {
        const result = await apiFetch<IdeaGetResponse>(`/conversations/${conversation.id}/idea`, {
          method: "PATCH",
          body: ideaData,
        });
        setProjectDraft(result.idea);
      } catch (error) {
        // eslint-disable-next-line no-console
        console.error("Failed to update idea:", error);
        throw error;
      } finally {
        setIsUpdating(false);
      }
    },
    [conversation.id]
  );

  // Load initial data
  useEffect(() => {
    const loadData = async (): Promise<void> => {
      try {
        const draftResult = await apiFetch<IdeaGetResponse>(
          `/conversations/${conversation.id}/idea`
        );
        setProjectDraft(draftResult.idea);
      } catch (error) {
        // eslint-disable-next-line no-console
        console.error("Failed to load data:", error);
      } finally {
        setIsLoading(false);
      }
    };

    loadData();
  }, [conversation.id]);

  // Poll for idea updates when idea is being generated
  useEffect(() => {
    const checkAndPoll = async () => {
      try {
        const result = await apiFetch<IdeaGetResponse>(`/conversations/${conversation.id}/idea`);
        const draft = result.idea;
        setProjectDraft(draft);

        // Only continue polling if idea is still being generated
        if (isIdeaGenerating(draft)) {
          return true; // Continue polling
        }
      } catch (error) {
        // eslint-disable-next-line no-console
        console.error("Polling error:", error);
      }
      return false; // Stop polling
    };

    const pollInterval = setInterval(async () => {
      const shouldContinue = await checkAndPoll();
      if (!shouldContinue) {
        clearInterval(pollInterval);
      }
    }, constants.POLL_INTERVAL_MS);

    return () => {
      clearInterval(pollInterval);
    };
  }, [conversation.id]);

  return {
    projectDraft,
    setProjectDraft,
    isLoading,
    isUpdating,
    updateProjectDraft,
  };
}
