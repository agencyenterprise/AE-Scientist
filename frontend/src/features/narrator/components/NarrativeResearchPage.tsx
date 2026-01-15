"use client";

import { DebugPanel } from "@/features/narrator/components/debug/DebugPanel";
import { ScrollToLatestButton } from "@/features/narrator/components/timeline/ScrollToLatestButton";
import {
  TimelineView,
  type TimelineViewHandle,
} from "@/features/narrator/components/timeline/TimelineView";
import {
  formatProgress,
  getCurrentFocus,
  getCurrentStage,
  getOverallProgress,
  getRunId,
  getStatus,
} from "@/features/narrator/lib/narratorSelectors";
import { useResource } from "@/features/narrator/systems/narrative";
import { TimelineEvent } from "@/features/narrator/systems/resources/narratorStore";
import { Throttler, useDebouncer } from "@tanstack/react-pacer";
import { useCallback, useEffect, useRef, useState } from "react";

const statusMap = {
  connected: "Connected",
  connecting: "Connecting...",
  disconnected: "Disconnected",
  error: "Error",
};

const colorMap = {
  connected: "bg-emerald-500",
  connecting: "bg-yellow-500 animate-pulse",
  disconnected: "bg-red-500",
  error: "bg-red-500",
};

export default function NarrativePage({ runId }: { runId: string }) {
  // Get store resource to access Zustand store
  const narratorStore = useResource("narratorStore");
  narratorStore.useRunId(runId); // setup store with runId

  const sseStream = useResource("sseStream");

  // Refs for scroll control
  const timelineRef = useRef<TimelineViewHandle>(null);
  const [showScrollButton, setShowScrollButton] = useState(false);

  // Use the store hook to get reactive state
  const state = narratorStore.useStore(s => s.researchState);
  const connectionStatus = narratorStore.useStore(s => s.connectionStatus);
  const error = narratorStore.useStore(s => s.error);
  const expandedStages = narratorStore.useStore(s => s.uiState.expandedStages);
  const focusedEventId = narratorStore.useStore(s => s.uiState.focusedEventId);
  const shouldAutoScroll = narratorStore.useStore(s => s.uiState.shouldAutoScroll);

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

  // Handle event focus
  const handleEventFocus = useCallback(
    (eventId: string | null) => {
      narratorStore.patchUiState({
        focusedEventId: eventId,
        shouldAutoScroll: eventId === null, // Disable auto-scroll when focused
      });
    },
    [narratorStore]
  );

  // Handle scroll to latest button click
  const handleScrollToLatest = useCallback(() => {
    narratorStore.patchUiState({
      focusedEventId: null,
      shouldAutoScroll: true,
    });
    timelineRef.current?.scrollToBottom(true);
  }, [narratorStore]);

  // Check scroll position and update button visibility
  useEffect(() => {
    if (!timelineRef.current) return;

    const checkScrollPosition = () => {
      const isNearBottom = timelineRef.current?.isNearBottom(100) ?? false;

      if (!focusedEventId && !isNearBottom) {
        setShowScrollButton(true);
        return;
      }
      // Show button if user is focused on an event and not near bottom
      if (focusedEventId !== null && !isNearBottom) {
        setShowScrollButton(true);
        return;
      }

      // All other cases, hide button
      setShowScrollButton(false);
    };

    const throttledCheck = new Throttler(checkScrollPosition, {
      wait: 150,
      enabled: true,
    });

    // Initial check
    checkScrollPosition();

    // Subscribe to scroll events through the timeline API
    const unsubscribe = timelineRef.current.onScroll(() => throttledCheck.maybeExecute());
    return () => {
      unsubscribe();
      throttledCheck.cancel();
    };
  }, [focusedEventId]);

  const scrollToLatest = useCallback(
    (_event: TimelineEvent) => {
      const currentResearchState = narratorStore.getResearchState();
      if (!currentResearchState?.timeline || currentResearchState.timeline.length === 0) {
        return; // no timeline data, skip
      }
      if (!shouldAutoScroll) {
        return;
      }

      const isNearBottom = timelineRef.current?.isNearBottom(100);

      if (!isNearBottom) {
        timelineRef.current?.scrollToBottom(true);
      }
    },
    [narratorStore, shouldAutoScroll]
  );

  const debouncedScrollToLatest = useDebouncer(scrollToLatest, {
    wait: 500,
    enabled: (state?.timeline?.length ?? 0) > 0 && shouldAutoScroll,
  });

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
        debouncedScrollToLatest.maybeExecute(event);
      },
      [narratorStore, toggleExpanded, debouncedScrollToLatest]
    )
  );

  // Handle node selection (for future tree view integration)
  const handleViewNode = (nodeId: string) => {
    // TODO: When tree view is integrated, scroll to and highlight this node
    // For now, we just prepare the handler for future use
    void nodeId;
  };

  const connectionStatusText = statusMap[connectionStatus];
  const connectionStatusColor = colorMap[connectionStatus];

  return (
    <div className="container mx-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold text-white">Research Run Narrative</h1>
        <div className="flex items-center gap-2">
          <div className={`w-3 h-3 rounded-full ${connectionStatusColor}`} />
          <span className="text-sm text-slate-300">{connectionStatusText}</span>
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

      <div className="bg-slate-900/50 py-2 relative">
        <h2 className="text-xl font-semibold text-white mb-6">Research Timeline</h2>
        <TimelineView
          ref={timelineRef}
          state={state}
          isLoading={
            connectionStatus === "connecting" && (!state || (state?.timeline?.length ?? 0) === 0)
          }
          onViewNode={handleViewNode}
          expandedStages={expandedStages}
          toggleExpanded={toggleExpanded}
          onEventFocus={handleEventFocus}
        >
          <ScrollToLatestButton visible={showScrollButton} onClick={handleScrollToLatest} />
        </TimelineView>
      </div>

      {/* Floating Debug Panel (dev only) */}
      <DebugPanel state={state} />
    </div>
  );
}

/**
 * System boundary component for the narrative page.
 * used in the layout file to ensure that the narrative system is cleaned up when the page is unmounted.
 */
export function NarrativeSystemBoundary() {
  const { useCleanup } = useResource("cleanup");
  useCleanup();
  return null;
}
