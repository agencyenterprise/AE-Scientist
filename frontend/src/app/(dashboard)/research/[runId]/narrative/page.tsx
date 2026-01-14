"use client";

import { useParams } from "next/navigation";
import { useEffect, useMemo } from "react";
import { useNarrativeStream } from "@/features/research/hooks/useNarrativeStream";
import { useNarratorStore } from "@/features/research/stores/narratorStore";
import {
  getCurrentStage,
  getCurrentFocus,
  getOverallProgress,
  getStatus,
  getRunId,
  formatProgress,
} from "@/features/research/lib/narratorSelectors";

export default function NarrativePage() {
  const params = useParams();
  const runId = params?.runId as string;

  const { state, events, connectionStatus, error, reset } = useNarratorStore();

  // Connect to SSE stream
  const callbacks = useMemo(
    () => ({
      onStateSnapshot: useNarratorStore.getState().setState,
      onTimelineEvent: useNarratorStore.getState().addEvent,
      onStateDelta: useNarratorStore.getState().updatePartialState,
      onConnectionStatusChange: useNarratorStore.getState().setConnectionStatus,
      onError: useNarratorStore.getState().setError,
    }),
    []
  );

  useNarrativeStream(runId, callbacks);

  // Reset store on unmount
  useEffect(() => {
    return () => {
      reset();
    };
  }, [reset]);

  // Compute derived values using selectors
  const currentStage = getCurrentStage(state);
  const currentFocus = getCurrentFocus(state);
  const progress = getOverallProgress(state);
  const status = getStatus(state);
  const stateRunId = getRunId(state);

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

      <div className="bg-slate-900/50 border border-slate-700/80 rounded-lg p-6">
        <h2 className="text-xl font-semibold text-white mb-4">
          Timeline Events ({events.length})
        </h2>
        <div className="space-y-3 max-h-[600px] overflow-y-auto">
          {events.length === 0 ? (
            <p className="text-slate-400 text-center py-8">
              {connectionStatus === "connected"
                ? "No events yet. Waiting for timeline events..."
                : "Connecting to event stream..."}
            </p>
          ) : (
            events.map((event, idx) => (
              <div
                key={event.id || idx}
                className="border-l-4 border-emerald-500 pl-4 py-2"
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-sm text-white">{event.type}</span>
                      {event.stage && (
                        <span className="text-xs bg-slate-700/50 text-slate-300 px-2 py-1 rounded">
                          {event.stage}
                        </span>
                      )}
                    </div>
                    {event.headline && (
                      <p className="text-slate-300 mt-1">{event.headline}</p>
                    )}
                  </div>
                  <span className="text-xs text-slate-500">
                    {new Date(event.timestamp).toLocaleTimeString()}
                  </span>
                </div>
              </div>
            ))
          )}
        </div>
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

