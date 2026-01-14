import { create } from "zustand";
import type { components } from "@/types/api.gen";

// Use generated types from OpenAPI schema
type ResearchRunState = components["schemas"]["ResearchRunState"];
type TimelineEvent = NonNullable<ResearchRunState["timeline"]>[number];
type ConnectionStatus = "connecting" | "connected" | "disconnected" | "error";

interface NarratorStore {
  // State
  state: ResearchRunState | null;
  events: TimelineEvent[];
  isConnected: boolean;
  connectionStatus: ConnectionStatus;
  error: string | null;

  // Actions (data-only, no computation)
  setState: (state: ResearchRunState) => void;
  addEvent: (event: TimelineEvent) => void;
  updatePartialState: (updates: Partial<ResearchRunState>) => void;
  setError: (error: string | null) => void;
  setConnectionStatus: (status: ConnectionStatus) => void;
  reset: () => void;
}

export const useNarratorStore = create<NarratorStore>((set) => ({
  // Initial state
  state: null,
  events: [],
  isConnected: false,
  connectionStatus: "connecting",
  error: null,

  // Actions
  setState: (state) =>
    set({
      state,
      error: null,
    }),

  addEvent: (event) =>
    set((prev) => ({
      events: [...prev.events, event],
    })),

  updatePartialState: (updates) =>
    set((prev) => {
      if (!prev.state) return prev;

      return {
        state: {
          ...prev.state,
          ...updates,
        },
      };
    }),

  setError: (error) => set({ error }),

  setConnectionStatus: (status) =>
    set({
      connectionStatus: status,
      isConnected: status === "connected",
    }),

  reset: () =>
    set({
      state: null,
      events: [],
      isConnected: false,
      connectionStatus: "connecting",
      error: null,
    }),
}));

