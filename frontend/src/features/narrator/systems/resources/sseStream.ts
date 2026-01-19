import { parseNarratorSseFrame, readSseFrames, SseFrame } from "@/features/narrator/lib/sse";
import { config, isDevelopment } from "@/shared/lib/config";
import { withAuthHeaders } from "@/shared/lib/session-token";
import { createSubscription, SubscriptionCallback } from "@/shared/lib/subscription";
import { Debouncer } from "@tanstack/react-pacer";
import { defineResource, StartedResource } from "braided";
import { useEffect } from "react";
import {
  connectionStatusKeywords,
  NarratorStoreResource,
  ResearchRunState,
  TimelineEvent,
} from "./narratorStore";

type EventHandlers = {
  state_snapshot: (data: ResearchRunState) => void;
  timeline_event: (data: TimelineEvent) => void;
  state_delta: (data: Partial<ResearchRunState>) => void;
  ping: () => void;
  unknown: (frame: SseFrame) => void;
};

/**
 * Dispatches a parsed SSE event to the appropriate handler.
 * Handles JSON parsing and error recovery.
 */
function dispatchEvent(frame: SseFrame, handlers: EventHandlers): void {
  const { event, data } = frame;

  try {
    const parsed = event === "ping" ? undefined : JSON.parse(data);
    const handler = handlers[event as keyof EventHandlers];
    if (handler) {
      handler(parsed);
    } else {
      handlers.unknown(frame);
    }
  } catch (err) {
    // eslint-disable-next-line no-console
    console.error(`[SSE] Error dispatching event '${event}':`, err);
  }
}

/**
 * Resource that manages the SSE connection to the narrative stream.
 * Depends on the narrator store to dispatch events.
 *
 * handles:
 * - Connection lifecycle
 * - Abort control
 * - Reconnection logic
 * - HTTP concerns (auth, status codes)
 */
export const sseStreamResource = defineResource({
  dependencies: ["narratorStore"],
  start: async ({ narratorStore }: { narratorStore: NarratorStoreResource }) => {
    const maxReconnectAttempts = 5;
    const state = {
      currentAbortController: null as AbortController | null,
      currentRunId: null as string | null,
      reconnectAttempts: 0,
      reconnectTimeoutId: null as ReturnType<typeof setTimeout> | null,
      accumulatedEvents: [] as TimelineEvent[],
    };

    const eventSubscription = createSubscription<TimelineEvent>();

    // Commit accumulated events to store and notify subscribers
    const commitEvents = () => {
      if (state.accumulatedEvents.length === 0) return;

      const eventsToCommit = [...state.accumulatedEvents];
      state.accumulatedEvents = [];

      // Add all events to store
      narratorStore.addEvents(eventsToCommit);

      // Notify subscribers for each event
      for (const event of eventsToCommit) {
        eventSubscription.notify(event);
      }

      if (isDevelopment) {
        // eslint-disable-next-line no-console
        console.log(`[Narrator SSE] Committed ${eventsToCommit.length} events`);
      }
    };

    // Debounced commit - waits 200ms after last event before committing
    // This helps reduce UI reflow when multiple events are received in quick succession.
    const debouncedCommit = new Debouncer(commitEvents, {
      wait: 200,
      enabled: true,
    });

    // Domain-specific event handlers
    const handlers: EventHandlers = {
      state_snapshot: (stateData: ResearchRunState) => {
        narratorStore.setResearchState(stateData);
      },
      timeline_event: (event: TimelineEvent) => {
        // Accumulate event and trigger debounced commit
        state.accumulatedEvents.push(event);
        debouncedCommit.maybeExecute();
      },
      state_delta: (delta: Partial<ResearchRunState>) => {
        narratorStore.patchResearchState(delta);
      },
      ping: () => {
        // no-op
      },
      unknown: (frame: SseFrame) => {
        // no-op
        if (isDevelopment) {
          // eslint-disable-next-line no-console
          console.log("[Narrator] Unknown event:", frame);
        }
      },
    };

    const api = {
      setupForRun: (runId: string) => {
        api.stopCurrentStream();
        state.currentAbortController = new AbortController();
        state.currentRunId = runId;
        narratorStore.setConnectionStatus(connectionStatusKeywords.disconnected);
      },
      connectToStream: async (runId: string) => {
        if (state.currentRunId === runId && narratorStore.isConnected()) {
          return; // already connected to this run, do nothing
        }

        api.setupForRun(runId);

        try {
          narratorStore.setConnectionStatus(connectionStatusKeywords.connecting);

          const response = await fetch(`${config.apiUrl}/research-runs/${runId}/narrative-stream`, {
            headers: withAuthHeaders(new Headers({ Accept: "text/event-stream" })),
            signal: state.currentAbortController?.signal,
          });

          // HTTP error handling
          if (!response.ok) {
            if (response.status === 401) {
              window.location.href = "/login";
              return;
            }
            throw new Error(`HTTP ${response.status}`);
          }

          if (!response.body) {
            throw new Error("No response body");
          }

          state.reconnectAttempts = 0;
          if (!narratorStore.isConnected()) {
            narratorStore.setConnectionStatus(connectionStatusKeywords.connected);
          }

          if (isDevelopment) {
            // eslint-disable-next-line no-console
            console.log("[Narrator SSE] Connection established");
          }

          for await (const rawFrame of readSseFrames(
            response.body,
            state.currentAbortController?.signal
          )) {
            const frame = parseNarratorSseFrame(rawFrame);
            if (!frame) continue;

            dispatchEvent(frame, handlers);
          }

          if (isDevelopment) {
            // eslint-disable-next-line no-console
            console.log("[Narrator SSE] Stream ended gracefully");
          }
          // Flush any pending events before disconnecting
          debouncedCommit.cancel();
          commitEvents();
          narratorStore.setConnectionStatus(connectionStatusKeywords.disconnected);
        } catch (err) {
          if (err instanceof Error && err.name === "AbortError") {
            api.cleanup();
            return;
          }

          const errorMessage = err instanceof Error ? err.message : "Connection failed";

          // Attempt reconnection with exponential backoff
          if (state.reconnectAttempts < maxReconnectAttempts) {
            const delay = Math.min(1000 * Math.pow(2, state.reconnectAttempts), 30000);
            state.reconnectAttempts++;

            if (isDevelopment) {
              // eslint-disable-next-line no-console
              console.log(
                `[Narrator SSE] Connection failed: ${errorMessage}. Reconnection attempt ${state.reconnectAttempts}/${maxReconnectAttempts} in ${delay}ms`
              );
            }

            narratorStore.setConnectionStatus(connectionStatusKeywords.connecting);

            state.reconnectTimeoutId = setTimeout(() => {
              if (state.currentRunId) {
                api.connectToStream(state.currentRunId);
              }
            }, delay);
          } else {
            // eslint-disable-next-line no-console
            console.error(
              "[Narrator SSE] Max reconnection attempts reached. Connection permanently lost."
            );
            narratorStore.setError("Max reconnection attempts reached. Please refresh the page.");
            narratorStore.setConnectionStatus(connectionStatusKeywords.error);
          }
        }
      },

      reconnectStream: () => {
        const storeState = narratorStore.useStore.getState();
        if (storeState.runId) {
          // Reset reconnection attempts for manual reconnect
          state.reconnectAttempts = 0;
          api.connectToStream(storeState.runId);
        } else {
          // eslint-disable-next-line no-console
          console.error("[Narrator SSE] No runId found");
        }
      },

      stopCurrentStream: () => {
        if (state.currentAbortController) {
          state.currentAbortController.abort();
        }
        api.cleanup();
      },

      cleanup: () => {
        if (state.reconnectTimeoutId) {
          clearTimeout(state.reconnectTimeoutId);
          state.reconnectTimeoutId = null;
        }
        // Flush any pending events before cleanup
        debouncedCommit.cancel();
        commitEvents();
        state.currentAbortController = null;
        state.currentRunId = null;
        narratorStore.setConnectionStatus(connectionStatusKeywords.disconnected);
      },

      // Hooks
      useEventSubscription: (observerFn: SubscriptionCallback<typeof eventSubscription>) => {
        return useEffect(() => {
          const unsubscribe = eventSubscription.subscribe(observerFn);
          return () => unsubscribe();
        }, [observerFn]);
      },
    };

    // Start connection when runId changes
    narratorStore.useStore.subscribe(
      state => state.runId,
      runId => {
        if (runId) {
          api.connectToStream(runId);
        }
      }
    );

    return {
      isConnected: narratorStore.isConnected,
      reconnectStream: api.reconnectStream,
      stopCurrentStream: api.stopCurrentStream,
      useEventSubscription: api.useEventSubscription,
    };
  },
  halt: instance => {
    instance.stopCurrentStream();
  },
});

export type SseStreamResource = StartedResource<typeof sseStreamResource>;
