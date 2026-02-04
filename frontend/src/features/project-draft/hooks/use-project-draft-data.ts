"use client";

import { useState, useEffect, useCallback } from "react";
import type { ConversationDetail, Idea } from "@/types";
import { api } from "@/shared/lib/api-client-typed";
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
  updateProjectDraft: (ideaData: { title: string; idea_markdown: string }) => Promise<void>;
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
    async (ideaData: { title: string; idea_markdown: string }): Promise<void> => {
      setIsUpdating(true);
      try {
        const { data, error } = await api.PATCH("/api/conversations/{conversation_id}/idea", {
          params: { path: { conversation_id: conversation.id } },
          body: ideaData,
        });

        if (error) {
          throw new Error("Failed to update idea");
        }

        if (data && "idea" in data) {
          setProjectDraft((data.idea as Idea) || null);
        }
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
      const { data } = await api.GET("/api/conversations/{conversation_id}/idea", {
        params: { path: { conversation_id: conversation.id } },
      });

      // 404 means idea is still being generated - don't treat as error
      // Other errors are silently ignored since polling will handle recovery
      if (data && "idea" in data) {
        setProjectDraft((data.idea as Idea) || null);
      }
      // If 404 or error, projectDraft stays null - polling will pick it up

      setIsLoading(false);
    };

    loadData();
  }, [conversation.id]);

  // Poll for idea updates when idea is being generated or doesn't exist yet
  useEffect(() => {
    const checkAndPoll = async () => {
      const { data, error } = await api.GET("/api/conversations/{conversation_id}/idea", {
        params: { path: { conversation_id: conversation.id } },
      });

      // 404 means idea is still being generated - continue polling
      // Other errors also continue polling to allow recovery
      if (error) {
        // Idea doesn't exist yet or temporary error - continue polling
        return true;
      }

      const draft = data && "idea" in data ? (data.idea as Idea) : null;
      setProjectDraft(draft);

      // Only continue polling if idea is still being generated
      if (isIdeaGenerating(draft)) {
        return true; // Continue polling
      }

      return false; // Stop polling - idea is complete
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
