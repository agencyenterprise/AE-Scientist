import { useEffect, useRef } from "react";
import { config } from "@/shared/lib/config";
import { withAuthHeaders } from "@/shared/lib/session-token";
import type { components } from "@/types/api.gen";

// Use generated types from OpenAPI schema
type ResearchRunState = components["schemas"]["ResearchRunState"];
type TimelineEvent = NonNullable<ResearchRunState["timeline"]>[number];
type ConnectionStatus = "connecting" | "connected" | "disconnected" | "error";

interface UseNarrativeStreamCallbacks {
  onStateSnapshot: (state: ResearchRunState) => void;
  onTimelineEvent: (event: TimelineEvent) => void;
  onStateDelta: (delta: Partial<ResearchRunState>) => void;
  onConnectionStatusChange: (status: ConnectionStatus) => void;
  onError: (error: string | null) => void;
}

/**
 * Hook to manage SSE connection to narrative stream endpoint.
 * 
 * Handles connection lifecycle, parsing SSE events, and dispatching to callbacks.
 * Prevents double-connection in React StrictMode.
 */
export function useNarrativeStream(
  runId: string | undefined,
  callbacks: UseNarrativeStreamCallbacks
) {
  const abortControllerRef = useRef<AbortController | null>(null);
  const isConnectingRef = useRef(false);

  useEffect(() => {
    if (!runId) return;

    // Prevent double connection in React StrictMode
    if (isConnectingRef.current) {
      console.log("[Narrator SSE] Already connecting, skipping duplicate mount");
      return;
    }

    isConnectingRef.current = true;

    const controller = new AbortController();
    abortControllerRef.current = controller;

    const connectToStream = async () => {
      try {
        callbacks.onConnectionStatusChange("connecting");

        const response = await fetch(
          `${config.apiUrl}/research-runs/${runId}/narrative-stream`,
          {
            headers: withAuthHeaders(new Headers({ Accept: "text/event-stream" })),
            signal: controller.signal,
          }
        );

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

        callbacks.onConnectionStatusChange("connected");
        console.log("[Narrator SSE] Connection established");

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });

          // Split by double newline (SSE event separator)
          const parts = buffer.split("\n\n");
          buffer = parts.pop() || "";

          for (const part of parts) {
            if (!part.trim()) continue;

            // Parse SSE format: "event: type\ndata: json"
            const lines = part.split("\n");
            let eventType = "message";
            let eventData = "";

            for (const line of lines) {
              if (line.startsWith("event: ")) {
                eventType = line.slice(7);
              } else if (line.startsWith("data: ")) {
                eventData = line.slice(6);
              }
            }

            if (!eventData) continue;

            try {
              switch (eventType) {
                case "state_snapshot": {
                  const stateData = JSON.parse(eventData) as ResearchRunState;
                  callbacks.onStateSnapshot(stateData);
                  console.log("[Narrator] State snapshot:", stateData);
                  break;
                }
                case "timeline_event": {
                  const event = JSON.parse(eventData) as TimelineEvent;
                  callbacks.onTimelineEvent(event);
                  console.log("[Narrator] Timeline event:", event);
                  break;
                }
                case "state_delta": {
                  const delta = JSON.parse(eventData) as Partial<ResearchRunState>;
                  callbacks.onStateDelta(delta);
                  console.log("[Narrator] State delta:", delta);
                  break;
                }
                case "ping": {
                  console.log("[Narrator] Keepalive ping");
                  break;
                }
                default:
                  console.log(`[Narrator] Unknown event type: ${eventType}`);
              }
            } catch (err) {
              console.error(`[Narrator] Error parsing ${eventType}:`, err);
            }
          }
        }

        console.log("[Narrator SSE] Stream ended");
        callbacks.onConnectionStatusChange("disconnected");
      } catch (err) {
        if (err instanceof Error && err.name === "AbortError") {
          console.log("[Narrator SSE] Connection aborted");
          return;
        }
        console.error("[Narrator SSE] Connection error:", err);
        callbacks.onConnectionStatusChange("error");
        callbacks.onError("Connection lost. Please refresh the page.");
      }
    };

    connectToStream();

    return () => {
      console.log("[Narrator SSE] Cleanup - aborting connection");
      controller.abort();
      isConnectingRef.current = false;
      callbacks.onConnectionStatusChange("disconnected");
    };
  }, [runId, callbacks]);
}

