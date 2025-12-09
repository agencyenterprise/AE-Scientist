import { useState, useCallback } from "react";
import type { Idea, IdeaGetResponse } from "@/types";
import { apiFetch } from "@/shared/lib/api-client";

// Section types
export type StringSection =
  | "title"
  | "hypothesis"
  | "related_work"
  | "abstract"
  | "expected_outcome";
export type ArraySection = "experiments" | "risk_factors";
export type SectionType = StringSection | ArraySection;

// Map section names to API field names
const SECTION_TO_FIELD: Record<SectionType, string> = {
  title: "title",
  hypothesis: "short_hypothesis",
  related_work: "related_work",
  abstract: "abstract",
  expected_outcome: "expected_outcome",
  experiments: "experiments",
  risk_factors: "risk_factors_and_limitations",
};

// Map section names to display titles
export const SECTION_TITLES: Record<SectionType, string> = {
  title: "Title",
  hypothesis: "Research Hypothesis",
  related_work: "Related Work",
  abstract: "Abstract",
  expected_outcome: "Expected Outcome",
  experiments: "Experiments",
  risk_factors: "Risk Factors & Limitations",
};

// Item labels for array sections
export const ARRAY_ITEM_LABELS: Record<ArraySection, string> = {
  experiments: "Experiment",
  risk_factors: "Risk Factor",
};

interface UseSectionEditOptions {
  conversationId: string;
  projectDraft: Idea | null;
  onUpdate: (updatedIdea: Idea) => void;
}

interface UseSectionEditReturn {
  // Modal state
  activeSection: SectionType | null;
  activeItemIndex: number | null;
  isEditingAllItems: boolean;
  isAddingNewItem: boolean;

  // Open/close modals
  openSection: (section: StringSection) => void;
  openArrayItem: (section: ArraySection, index: number) => void;
  openArrayAll: (section: ArraySection) => void;
  openAddNewItem: (section: ArraySection) => void;
  close: () => void;

  // Get current content for editing
  getStringContent: (section: StringSection) => string;
  getArrayContent: (section: ArraySection) => string[];

  // Save functions
  saveString: (section: StringSection, value: string) => Promise<void>;
  saveArray: (section: ArraySection, items: string[]) => Promise<void>;
  saveNewArrayItem: (section: ArraySection, value: string) => Promise<void>;

  // Direct array manipulation (without modal)
  deleteArrayItem: (section: ArraySection, index: number) => Promise<void>;

  // State
  isSaving: boolean;
  error: string | null;
  clearError: () => void;
}

export function useSectionEdit({
  conversationId,
  projectDraft,
  onUpdate,
}: UseSectionEditOptions): UseSectionEditReturn {
  const [activeSection, setActiveSection] = useState<SectionType | null>(null);
  const [activeItemIndex, setActiveItemIndex] = useState<number | null>(null);
  const [isEditingAllItems, setIsEditingAllItems] = useState(false);
  const [isAddingNewItem, setIsAddingNewItem] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Build the full payload for API update
  const buildPayload = useCallback(
    (updates: Partial<Record<string, string | string[]>>) => {
      if (!projectDraft?.active_version) {
        throw new Error("No active version to update");
      }

      const activeVersion = projectDraft.active_version;

      return {
        title: activeVersion.title,
        short_hypothesis: activeVersion.short_hypothesis,
        related_work: activeVersion.related_work,
        abstract: activeVersion.abstract,
        experiments: activeVersion.experiments,
        expected_outcome: activeVersion.expected_outcome,
        risk_factors_and_limitations: activeVersion.risk_factors_and_limitations,
        ...updates,
      };
    },
    [projectDraft]
  );

  // API call to update the idea
  const updateIdea = useCallback(
    async (payload: ReturnType<typeof buildPayload>): Promise<void> => {
      const result = await apiFetch<IdeaGetResponse>(`/conversations/${conversationId}/idea`, {
        method: "PATCH",
        body: payload,
      });
      onUpdate(result.idea);
    },
    [conversationId, onUpdate]
  );

  // Open section for editing (string sections)
  const openSection = useCallback((section: StringSection): void => {
    setActiveSection(section);
    setActiveItemIndex(null);
    setIsEditingAllItems(false);
    setIsAddingNewItem(false);
    setError(null);
  }, []);

  // Open single array item for editing
  const openArrayItem = useCallback((section: ArraySection, index: number): void => {
    setActiveSection(section);
    setActiveItemIndex(index);
    setIsEditingAllItems(false);
    setIsAddingNewItem(false);
    setError(null);
  }, []);

  // Open all array items for editing
  const openArrayAll = useCallback((section: ArraySection): void => {
    setActiveSection(section);
    setActiveItemIndex(null);
    setIsEditingAllItems(true);
    setIsAddingNewItem(false);
    setError(null);
  }, []);

  // Open modal to add a new array item
  const openAddNewItem = useCallback((section: ArraySection): void => {
    setActiveSection(section);
    setActiveItemIndex(null);
    setIsEditingAllItems(false);
    setIsAddingNewItem(true);
    setError(null);
  }, []);

  // Close modal
  const close = useCallback((): void => {
    setActiveSection(null);
    setActiveItemIndex(null);
    setIsEditingAllItems(false);
    setIsAddingNewItem(false);
    setError(null);
  }, []);

  // Get string content for a section
  const getStringContent = useCallback(
    (section: StringSection): string => {
      if (!projectDraft?.active_version) return "";

      const fieldName = SECTION_TO_FIELD[section];
      return (
        (projectDraft.active_version[
          fieldName as keyof typeof projectDraft.active_version
        ] as string) || ""
      );
    },
    [projectDraft]
  );

  // Get array content for a section
  const getArrayContent = useCallback(
    (section: ArraySection): string[] => {
      if (!projectDraft?.active_version) return [];

      const fieldName = SECTION_TO_FIELD[section];
      return (
        (projectDraft.active_version[
          fieldName as keyof typeof projectDraft.active_version
        ] as string[]) || []
      );
    },
    [projectDraft]
  );

  // Save string section
  const saveString = useCallback(
    async (section: StringSection, value: string): Promise<void> => {
      if (!projectDraft?.active_version) {
        throw new Error("No active version to update");
      }

      setIsSaving(true);
      setError(null);

      try {
        const fieldName = SECTION_TO_FIELD[section];
        const payload = buildPayload({ [fieldName]: value });
        await updateIdea(payload);
        close();
      } catch (err) {
        const errorMessage = err instanceof Error ? err.message : "Failed to save";
        setError(errorMessage);
        throw err;
      } finally {
        setIsSaving(false);
      }
    },
    [projectDraft, buildPayload, updateIdea, close]
  );

  // Save array section
  const saveArray = useCallback(
    async (section: ArraySection, items: string[]): Promise<void> => {
      if (!projectDraft?.active_version) {
        throw new Error("No active version to update");
      }

      setIsSaving(true);
      setError(null);

      try {
        const fieldName = SECTION_TO_FIELD[section];
        const payload = buildPayload({ [fieldName]: items });
        await updateIdea(payload);
        close();
      } catch (err) {
        const errorMessage = err instanceof Error ? err.message : "Failed to save";
        setError(errorMessage);
        throw err;
      } finally {
        setIsSaving(false);
      }
    },
    [projectDraft, buildPayload, updateIdea, close]
  );

  const clearError = useCallback((): void => {
    setError(null);
  }, []);

  // Save a new item to an array section (validates non-empty)
  const saveNewArrayItem = useCallback(
    async (section: ArraySection, value: string): Promise<void> => {
      if (!projectDraft?.active_version) {
        throw new Error("No active version to update");
      }

      const trimmedValue = value.trim();
      if (!trimmedValue) {
        setError("Content cannot be empty");
        throw new Error("Content cannot be empty");
      }

      setIsSaving(true);
      setError(null);

      try {
        const currentItems = getArrayContent(section);
        const newItems = [...currentItems, trimmedValue];
        const fieldName = SECTION_TO_FIELD[section];
        const payload = buildPayload({ [fieldName]: newItems });
        await updateIdea(payload);
        close();
      } catch (err) {
        const errorMessage = err instanceof Error ? err.message : "Failed to add item";
        setError(errorMessage);
        throw err;
      } finally {
        setIsSaving(false);
      }
    },
    [projectDraft, getArrayContent, buildPayload, updateIdea, close]
  );

  // Delete an item from an array section
  const deleteArrayItem = useCallback(
    async (section: ArraySection, index: number): Promise<void> => {
      if (!projectDraft?.active_version) {
        throw new Error("No active version to update");
      }

      setIsSaving(true);
      setError(null);

      try {
        const currentItems = getArrayContent(section);
        if (currentItems.length <= 1) {
          throw new Error("Cannot delete the last item");
        }
        const newItems = currentItems.filter((_, i) => i !== index);
        const fieldName = SECTION_TO_FIELD[section];
        const payload = buildPayload({ [fieldName]: newItems });
        await updateIdea(payload);
      } catch (err) {
        const errorMessage = err instanceof Error ? err.message : "Failed to delete item";
        setError(errorMessage);
        throw err;
      } finally {
        setIsSaving(false);
      }
    },
    [projectDraft, getArrayContent, buildPayload, updateIdea]
  );

  return {
    activeSection,
    activeItemIndex,
    isEditingAllItems,
    isAddingNewItem,
    openSection,
    openArrayItem,
    openArrayAll,
    openAddNewItem,
    close,
    getStringContent,
    getArrayContent,
    saveString,
    saveArray,
    saveNewArrayItem,
    deleteArrayItem,
    isSaving,
    error,
    clearError,
  };
}
