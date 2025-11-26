import { useState, useEffect, useCallback, useRef } from "react";
import type { ConversationDetail, Idea, IdeaGetResponse } from "@/types";
import { config, constants } from "@/lib/config";
import { isIdeaGenerating } from "../utils/versionUtils";

interface UseProjectDraftStateProps {
  conversation: ConversationDetail;
}

interface UseProjectDraftStateReturn {
  projectDraft: Idea | null;
  setProjectDraft: (draft: Idea) => void;
  isLoading: boolean;
  isEditing: boolean;
  setIsEditing: (editing: boolean) => void;
  editTitle: string;
  setEditTitle: (title: string) => void;
  editDescription: string;
  setEditDescription: (description: string) => void;
  isUpdating: boolean;
  isCreateModalOpen: boolean;
  setIsCreateModalOpen: (open: boolean) => void;
  isCreatingProject: boolean;
  setIsCreatingProject: (creating: boolean) => void;
  containerRef: React.RefObject<HTMLDivElement | null>;
  handleEdit: () => void;
  handleSave: () => Promise<void>;
  handleCancelEdit: () => void;
  handleKeyDown: (event: React.KeyboardEvent, action: () => void) => void;
  handleCreateProject: () => void;
  handleCloseCreateModal: () => void;
  handleConfirmCreateProject: () => Promise<void>;
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

export function useProjectDraftState({
  conversation,
}: UseProjectDraftStateProps): UseProjectDraftStateReturn {
  const [projectDraft, setProjectDraft] = useState<Idea | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isEditing, setIsEditing] = useState(false);
  const [editTitle, setEditTitle] = useState("");
  const [editDescription, setEditDescription] = useState("");
  const [isUpdating, setIsUpdating] = useState(false);
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [isCreatingProject, setIsCreatingProject] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

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
        const response = await fetch(`${config.apiUrl}/conversations/${conversation.id}/idea`, {
          method: "PATCH",
          headers: {
            "Content-Type": "application/json",
          },
          credentials: "include",
          body: JSON.stringify(ideaData),
        });

        if (response.ok) {
          const result: IdeaGetResponse = await response.json();
          setProjectDraft(result.idea);
          return;
        }
        const errorResult = await response.json();
        throw new Error(errorResult.error || "Failed to update idea");
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

  const handleEdit = (): void => {
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
  };

  const handleSave = async (): Promise<void> => {
    const trimmedTitle = editTitle.trim();
    const trimmedDescription = editDescription.trim();

    if (!trimmedTitle || !trimmedDescription) return;

    try {
      // Parse the JSON from editDescription
      const ideaData = JSON.parse(trimmedDescription);
      // Override title from the title field
      ideaData.title = trimmedTitle;
      await updateProjectDraft(ideaData);
      setIsEditing(false);
      setEditTitle("");
      setEditDescription("");
    } catch (error) {
      // eslint-disable-next-line no-console
      console.error("Failed to parse or save idea:", error);
      throw error;
    }
  };

  const handleCancelEdit = (): void => {
    setIsEditing(false);
    setEditTitle("");
    setEditDescription("");
  };

  const handleKeyDown = (event: React.KeyboardEvent, action: () => void): void => {
    if (event.key === "Enter" && event.ctrlKey) {
      action();
    } else if (event.key === "Escape") {
      handleCancelEdit();
    }
  };

  const handleCreateProject = (): void => {
    setIsCreateModalOpen(true);
  };

  const handleCloseCreateModal = (): void => {
    setIsCreateModalOpen(false);
  };

  const handleConfirmCreateProject = async (): Promise<void> => {
    // Project creation functionality removed (Linear integration removed)
    setIsCreateModalOpen(false);
  };

  // Load initial data
  useEffect(() => {
    const loadData = async (): Promise<void> => {
      try {
        // Load idea
        const draftResponse = await fetch(
          `${config.apiUrl}/conversations/${conversation.id}/idea`,
          {
            credentials: "include",
          }
        );
        if (draftResponse.ok) {
          const draftResult: IdeaGetResponse = await draftResponse.json();
          setProjectDraft(draftResult.idea);
        }
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
        const response = await fetch(`${config.apiUrl}/conversations/${conversation.id}/idea`, {
          credentials: "include",
        });
        if (response.ok) {
          const result: IdeaGetResponse = await response.json();
          const draft = result.idea;
          setProjectDraft(draft);

          // Only continue polling if idea is still being generated
          if (isIdeaGenerating(draft)) {
            return true; // Continue polling
          }
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

  // Scroll to bottom when component mounts or project draft loads
  useEffect(() => {
    if (containerRef.current && !isLoading) {
      // Scroll to bottom after a brief delay to ensure content is rendered
      setTimeout(() => {
        if (containerRef.current) {
          containerRef.current.scrollTop = containerRef.current.scrollHeight;
        }
      }, 100);
    }
  }, [isLoading, projectDraft]);

  return {
    projectDraft,
    setProjectDraft,
    isLoading,
    isEditing,
    setIsEditing,
    editTitle,
    setEditTitle,
    editDescription,
    setEditDescription,
    isUpdating,
    isCreateModalOpen,
    setIsCreateModalOpen,
    isCreatingProject,
    setIsCreatingProject,
    containerRef,
    handleEdit,
    handleSave,
    handleCancelEdit,
    handleKeyDown,
    handleCreateProject,
    handleCloseCreateModal,
    handleConfirmCreateProject,
    updateProjectDraft,
  };
}
