"use client";

import {
  formatProgress,
  getCurrentFocus,
  getCurrentStage,
  getOverallProgress,
  getRunId,
  getStatus,
} from "@/features/research/lib/narratorSelectors";
import { useResource } from "@/features/research/systems/narrative";
import { TimelineView } from "@/features/research/components/timeline/TimelineView";
import { useParams } from "next/navigation";
import { useCallback } from "react";
import { TimelineEvent } from "@/features/research/systems/resources/narratorStore";

export default function NarrativePage() {
  const params = useParams();
  const runId = params?.runId as string;

  // Get store resource to access Zustand store
  const narratorStore = useResource("narratorStore");
  narratorStore.useRunId(runId); // setup store with runId

  const sseStream = useResource("sseStream");

  // Use the store hook to get reactive state
  const state = narratorStore.useStore(s => s.researchState);
  const connectionStatus = narratorStore.useStore(s => s.connectionStatus);
  const error = narratorStore.useStore(s => s.error);
  const expandedStages = narratorStore.useStore(s => s.uiState.expandedStages);

  // Compute derived values using selectors
  const currentStage = getCurrentStage(state);
  const currentFocus = getCurrentFocus(state);
  const progress = getOverallProgress(state);
  const status = getStatus(state);
  const stateRunId = getRunId(state);

  const toggleExpanded = useCallback(
    (stageId: string) => {
      const currentState = narratorStore.getUiState();
      narratorStore.patchUiState({
        expandedStages: currentState.expandedStages.includes(stageId)
          ? currentState.expandedStages.filter(id => id !== stageId)
          : [...currentState.expandedStages, stageId],
      });
    },
    [narratorStore]
  );

  sseStream.useEventSubscription(
    useCallback(
      (event: TimelineEvent) => {
        switch (event.type) {
          case "stage_started":
            const currentState = narratorStore.getUiState();
            if (!currentState.expandedStages.includes(event.stage)) {
              toggleExpanded(event.stage);
            }
            break;
          default:
            // no-op
            break;
        }
      },
      [narratorStore, toggleExpanded]
    )
  );

  // Handle node selection (for future tree view integration)
  const handleViewNode = (nodeId: string) => {
    // TODO: When tree view is integrated, scroll to and highlight this node
    // For now, we just prepare the handler for future use
    void nodeId;
  };

  return (
    <div className="container mx-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold text-white">Research Run Narrative</h1>
        <div className="flex items-center gap-2">
          <div
            className={`w-3 h-3 rounded-full ${
              connectionStatus === "connected"
                ? "bg-emerald-500"
                : connectionStatus === "connecting"
                  ? "bg-yellow-500 animate-pulse"
                  : "bg-red-500"
            }`}
          />
          <span className="text-sm text-slate-300">
            {connectionStatus === "connected"
              ? "Connected"
              : connectionStatus === "connecting"
                ? "Connecting..."
                : "Disconnected"}
          </span>
        </div>
      </div>

      {error && (
        <div className="bg-red-950/50 border border-red-500/40 text-red-200 px-4 py-3 rounded-lg">
          {error}
        </div>
      )}

      {state && (
        <div className="bg-slate-900/50 border border-slate-700/80 rounded-lg p-6 space-y-4">
          <h2 className="text-xl font-semibold text-white">Current State</h2>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <span className="text-sm text-slate-400">Run ID:</span>
              <p className="font-mono text-sm text-slate-200">{stateRunId}</p>
            </div>
            <div>
              <span className="text-sm text-slate-400">Status:</span>
              <p className="font-semibold text-white">{status}</p>
            </div>
            {currentStage && (
              <div>
                <span className="text-sm text-slate-400">Current Stage:</span>
                <p className="text-slate-200">{currentStage}</p>
              </div>
            )}
            {currentFocus && (
              <div>
                <span className="text-sm text-slate-400">Current Focus:</span>
                <p className="text-slate-200">{currentFocus}</p>
              </div>
            )}
            {progress !== undefined && (
              <div>
                <span className="text-sm text-slate-400">Progress:</span>
                <p className="text-white font-semibold">{formatProgress(progress)}</p>
              </div>
            )}
          </div>
        </div>
      )}

      <div className="bg-slate-900/50 py-2">
        <h2 className="text-xl font-semibold text-white mb-6">Research Timeline</h2>
        <TimelineView
          state={state}
          isLoading={connectionStatus === "connecting" && !state}
          onViewNode={handleViewNode}
          expandedStages={expandedStages}
          toggleExpanded={toggleExpanded}
        />
      </div>

      <details className="bg-slate-900/50 border border-slate-700/80 rounded-lg p-4">
        <summary className="cursor-pointer font-semibold text-white">
          Debug: Raw State (JSON)
        </summary>
        <pre className="mt-4 text-xs text-slate-300 overflow-auto max-h-96">
          {JSON.stringify(state, null, 2)}
        </pre>
      </details>
    </div>
  );
}
