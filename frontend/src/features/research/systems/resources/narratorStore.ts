import { create } from "zustand";
import { subscribeWithSelector } from "zustand/middleware";
import type { components } from "@/types/api.gen";
import { useEffect } from "react";
import { defineResource, StartedResource } from "braided";

// generated types from OpenAPI schema
export type ResearchRunState = components["schemas"]["ResearchRunState"];
export type TimelineEvent = NonNullable<ResearchRunState["timeline"]>[number];

export const connectionStatusKeywords = {
  connecting: "connecting",
  connected: "connected",
  disconnected: "disconnected",
  error: "error",
} as const;

export type ConnectionStatus =
  (typeof connectionStatusKeywords)[keyof typeof connectionStatusKeywords];

type UIState = {
  expandedStages: string[];
  timelineFocused: boolean; // whether the user is focused/hovered on the timeline
};

type NarratorStore = {
  // State
  researchState: ResearchRunState | null;
  uiState: UIState;

  connectionStatus: ConnectionStatus;
  error: string | null;
  runId: string | null;

  // Actions (data-only, no computation)
  setResearchState: (state: ResearchRunState) => void;
  patchResearchState: (updates: Partial<ResearchRunState>) => void;
  patchUiState: (updates: Partial<UIState>) => void;
  setRunId: (runId: string) => void;
  addEvent: (event: TimelineEvent) => void;
  setError: (error: string | null) => void;
  setConnectionStatus: (status: ConnectionStatus) => void;
  reset: () => void;
};

export const createStore = () =>
  create<NarratorStore>()(
    subscribeWithSelector(set => ({
      // Initial state
      researchState: null,
      runId: null,
      uiState: {
        expandedStages: [],
        timelineFocused: false,
      },
      connectionStatus: connectionStatusKeywords.connecting,
      error: null,

      // Actions
      setResearchState: newState => {
        set({
          researchState: {
            ...newState,
            timeline: newState.timeline || [],
          },
          error: null,
        });
      },

      addEvent: event => {
        set(prevState => {
          if (!prevState.researchState) return prevState;

          // Idempotent: only add if event with this ID doesn't exist in timeline
          const timeline = prevState.researchState.timeline || [];
          const exists = timeline.some(e => e.id === event.id);
          if (exists) {
            return prevState; // No change
          }

          const updatedTimeline = [...timeline, event];
          return {
            researchState: {
              ...prevState.researchState,
              timeline: updatedTimeline,
            },
          };
        });
      },

      patchResearchState: updates =>
        set(prevState => {
          if (!prevState.researchState) {
            // invariant: cannot patch if we haven't got the full state yet
            return prevState;
          }

          return {
            researchState: {
              ...prevState.researchState,
              ...updates,
              // Timeline never changes as part of state patches
              timeline: prevState.researchState.timeline || [],
            },
          };
        }),

      patchUiState: updates => {
        set(prevState => ({
          uiState: {
            ...prevState.uiState,
            ...updates,
          },
        }));
      },

      setError: error => set({ error }),

      setConnectionStatus: status =>
        set({
          connectionStatus: status,
        }),

      reset: () =>
        set({
          researchState: null,
          connectionStatus: connectionStatusKeywords.connecting,
          error: null,
          runId: null,
        }),

      setRunId: runId =>
        set({
          runId,
        }),
    }))
  );

/**
 * Resource that manages the Zustand narrator store.
 * Provides access to store state and actions.
 */
export const narratorStoreResource = defineResource({
  start: () => {
    const useStore = createStore();
    const getState = useStore.getState;
    const getResearchState = () => getState().researchState;
    const getUiState = () => getState().uiState;
    const state = useStore.getState();

    return {
      // Expose store methods
      getState,
      getResearchState,
      getUiState,
      setResearchState: state.setResearchState,
      patchResearchState: state.patchResearchState,
      patchUiState: state.patchUiState,
      addEvent: state.addEvent,
      setError: state.setError,
      setConnectionStatus: state.setConnectionStatus,
      reset: state.reset,
      isConnected: () =>
        useStore.getState().connectionStatus === connectionStatusKeywords.connected,
      // Expose store hook for components
      useStore,
      useRunId: (runId: string) => {
        useEffect(() => {
          useStore.getState().setRunId(runId);
        }, [runId]);
      },
    };
  },
  halt: instance => {
    instance.reset();
  },
});

export type NarratorStoreResource = StartedResource<typeof narratorStoreResource>;
