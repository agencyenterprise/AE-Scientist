"use client";

import { useState, useCallback } from "react";
import type { Idea } from "@/types";

/**
 * Return type for the project draft edit hook.
 */
export interface UseProjectDraftEditReturn {
  /** Whether edit mode is active */
  isEditing: boolean;
  /** Set edit mode */
  setIsEditing: (editing: boolean) => void;
  /** Current edit title value */
  editTitle: string;
  /** Set edit title value */
  setEditTitle: (title: string) => void;
  /** Current edit description value (JSON) */
  editDescription: string;
  /** Set edit description value */
  setEditDescription: (description: string) => void;
  /** Start editing with current project draft data */
  handleEdit: (projectDraft: Idea | null) => void;
  /** Get the edited data for saving (returns null if invalid) */
  getEditedData: () => { title: string; ideaData: object } | null;
  /** Cancel edit mode */
  handleCancelEdit: () => void;
  /** Handle keyboard shortcuts in edit mode */
  handleKeyDown: (event: React.KeyboardEvent, saveAction: () => void) => void;
}

/**
 * Hook for managing project draft edit state.
 *
 * Extracted from useProjectDraftState to follow Single Responsibility Principle.
 * Handles:
 * - Edit mode state
 * - Title and description editing
 * - Keyboard shortcuts
 *
 * @example
 * ```typescript
 * const { isEditing, handleEdit, getEditedData, handleCancelEdit } = useProjectDraftEdit();
 *
 * const handleSave = async () => {
 *   const data = getEditedData();
 *   if (data) {
 *     await updateProjectDraft(data.ideaData);
 *   }
 * };
 *
 * return (
 *   <button onClick={() => handleEdit(projectDraft)}>Edit</button>
 * );
 * ```
 */
export function useProjectDraftEdit(): UseProjectDraftEditReturn {
  const [isEditing, setIsEditing] = useState(false);
  const [editTitle, setEditTitle] = useState("");
  const [editDescription, setEditDescription] = useState("");

  const handleEdit = useCallback((projectDraft: Idea | null): void => {
    if (!projectDraft?.active_version) return;

    setEditTitle(projectDraft.active_version.title || "");
    // Serialize all idea fields as JSON for editing
    const ideaJson = JSON.stringify(
      {
        title: projectDraft.active_version.title,
        short_hypothesis: projectDraft.active_version.short_hypothesis,
        related_work: projectDraft.active_version.related_work,
        abstract: projectDraft.active_version.abstract,
        experiments: projectDraft.active_version.experiments,
        expected_outcome: projectDraft.active_version.expected_outcome,
        risk_factors_and_limitations: projectDraft.active_version.risk_factors_and_limitations,
      },
      null,
      2
    );
    setEditDescription(ideaJson);
    setIsEditing(true);
  }, []);

  const getEditedData = useCallback((): { title: string; ideaData: object } | null => {
    const trimmedTitle = editTitle.trim();
    const trimmedDescription = editDescription.trim();

    if (!trimmedTitle || !trimmedDescription) return null;

    try {
      // Parse the JSON from editDescription
      const ideaData = JSON.parse(trimmedDescription);
      // Override title from the title field
      ideaData.title = trimmedTitle;
      return { title: trimmedTitle, ideaData };
    } catch (error) {
      // eslint-disable-next-line no-console
      console.error("Failed to parse idea JSON:", error);
      return null;
    }
  }, [editTitle, editDescription]);

  const handleCancelEdit = useCallback((): void => {
    setIsEditing(false);
    setEditTitle("");
    setEditDescription("");
  }, []);

  const handleKeyDown = useCallback(
    (event: React.KeyboardEvent, saveAction: () => void): void => {
      if (event.key === "Enter" && event.ctrlKey) {
        saveAction();
      } else if (event.key === "Escape") {
        handleCancelEdit();
      }
    },
    [handleCancelEdit]
  );

  return {
    isEditing,
    setIsEditing,
    editTitle,
    setEditTitle,
    editDescription,
    setEditDescription,
    handleEdit,
    getEditedData,
    handleCancelEdit,
    handleKeyDown,
  };
}
