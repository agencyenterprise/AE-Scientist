import { defineResource, StartedResource } from "braided";
import {
  connectionStatusKeywords,
  NarratorStoreResource,
  ResearchRunState,
  TimelineEvent,
} from "./narratorStore";
import { config, isDevelopment } from "@/shared/lib/config";
import { withAuthHeaders } from "@/shared/lib/session-token";
import { createSubscription, SubscriptionCallback } from "@/shared/lib/subscription";
import { useEffect } from "react";

interface SseFrame {
  event: string;
  data: string;
}

/**
 * Generator that reads SSE frames from a byte stream.
 *
 * Responsibilities:
 * - Buffer management
 * - Text decoding
 * - Frame boundary detection (\n\n)
 * - Cleanup on exit
 *
 * Does NOT know about:
 * - JSON parsing
 * - Event types
 * - Domain logic
 */
async function* readSseFrames(
  stream: ReadableStream<Uint8Array>,
  signal?: AbortSignal
): AsyncGenerator<string> {
  const reader = stream.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      // Check for cancellation
      if (signal?.aborted) {
        return;
      }

      const { value, done } = await reader.read();
      if (done) {
        return;
      }

      // Accumulate decoded text
      buffer += decoder.decode(value, { stream: true });

      // Yield complete frames
      let boundary;
      while ((boundary = buffer.indexOf("\n\n")) !== -1) {
        const frame = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);

        if (frame.trim()) {
          yield frame;
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}

/**
 * Parses a raw SSE frame string into structured event data.
 *
 * SSE format:
 *   event: event_type
 *   data: payload
 *
 * Returns null for invalid frames.
 */
function parseSseFrame(frame: string): SseFrame | null {
  const lines = frame.split("\n");
  let eventType = "message"; // SSE default
  let eventData = "";

  for (const line of lines) {
    if (line.startsWith("event: ")) {
      eventType = line.slice(7).trim();
    } else if (line.startsWith("data: ")) {
      eventData = line.slice(6);
    }
  }

  if (!eventData) {
    return null;
  }

  return { event: eventType, data: eventData };
}

type EventHandlers = {
  state_snapshot: (data: ResearchRunState) => void;
  timeline_event: (data: TimelineEvent) => void;
  state_delta: (data: Partial<ResearchRunState>) => void;
  ping: () => void;
  unknown: (eventType: string) => void;
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
      handlers.unknown(event);
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
  start: ({ narratorStore }: { narratorStore: NarratorStoreResource }) => {
    const maxReconnectAttempts = 5;
    const state = {
      currentAbortController: null as AbortController | null,
      currentRunId: null as string | null,
      reconnectAttempts: 0,
      reconnectTimeoutId: null as ReturnType<typeof setTimeout> | null,
    };

    const eventSubscription = createSubscription<TimelineEvent>();

    // Domain-specific event handlers
    const handlers: EventHandlers = {
      state_snapshot: (stateData: ResearchRunState) => {
        narratorStore.setResearchState(stateData);
      },
      timeline_event: (event: TimelineEvent) => {
        narratorStore.addEvent(event);
        eventSubscription.notify(event);
      },
      state_delta: (delta: Partial<ResearchRunState>) => {
        narratorStore.patchResearchState(delta);
      },
      ping: () => {
        // no-op
      },
      unknown: (_eventType: string) => {
        // no-op
        if (isDevelopment) {
          // eslint-disable-next-line no-console
          console.log("[Narrator] Unknown event type:", _eventType);
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
          narratorStore.setConnectionStatus(connectionStatusKeywords.connected);

          if (isDevelopment) {
            // eslint-disable-next-line no-console
            console.log("[Narrator SSE] Connection established");
          }

          for await (const rawFrame of readSseFrames(
            response.body,
            state.currentAbortController?.signal
          )) {
            const frame = parseSseFrame(rawFrame);
            if (!frame) continue;

            dispatchEvent(frame, handlers);
          }

          if (isDevelopment) {
            // eslint-disable-next-line no-console
            console.log("[Narrator SSE] Stream ended gracefully");
          }
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
            narratorStore.setConnectionStatus(connectionStatusKeywords.error);
            narratorStore.setError("Max reconnection attempts reached. Please refresh the page.");
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
        if (state.reconnectTimeoutId) {
          clearTimeout(state.reconnectTimeoutId);
          state.reconnectTimeoutId = null;
        }
        if (state.currentAbortController) {
          state.currentAbortController.abort();
          api.cleanup();
        }
      },

      cleanup: () => {
        if (state.reconnectTimeoutId) {
          clearTimeout(state.reconnectTimeoutId);
          state.reconnectTimeoutId = null;
        }
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
