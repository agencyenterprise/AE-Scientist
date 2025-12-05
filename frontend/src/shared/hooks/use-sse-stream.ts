"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { apiStream } from "@/shared/lib/api-client";

/**
 * Parser function type for converting raw SSE lines to events.
 * Different SSE endpoints use different formats:
 * - Import: JSON per line, no prefix
 * - Research: "data: " prefix with "\n\n" delimiter
 * - Chat: JSON per line, no prefix
 *
 * Return null to skip the line (e.g., empty lines or unparseable data).
 */
export type SSELineParser<T> = (line: string) => T | null;

/**
 * Options for the useSSEStream hook.
 */
export interface SSEStreamOptions<TEvent> {
  /** URL path for the SSE endpoint (will be prefixed with apiUrl) */
  url: string;
  /** HTTP method (default: 'GET') */
  method?: "GET" | "POST";
  /** Request body for POST requests */
  body?: object;
  /** Whether the stream should be active */
  enabled: boolean;
  /** Parse raw line into typed event (return null to skip) */
  parseEvent: SSELineParser<TEvent>;
  /** Handle parsed event */
  onEvent: (event: TEvent) => void;
  /** Called when stream completes normally */
  onComplete?: () => void;
  /** Called on error (connection or parsing) */
  onError?: (error: string) => void;
  /** Line delimiter (default: '\n') */
  delimiter?: string;
  /** Enable auto-reconnection on connection loss */
  reconnect?: boolean;
  /** Max reconnection attempts (default: 5) */
  maxReconnectAttempts?: number;
}

/**
 * Return type for the useSSEStream hook.
 */
export interface SSEStreamReturn {
  /** Whether the stream is currently connected */
  isConnected: boolean;
  /** Connection error message, if any */
  connectionError: string | null;
  /** Manually trigger reconnection */
  reconnect: () => void;
  /** Disconnect the stream */
  disconnect: () => void;
}

/**
 * Generic hook for SSE (Server-Sent Events) streaming.
 *
 * Handles:
 * - Buffer management and line parsing
 * - AbortController for cancellation
 * - Error handling with optional reconnection
 * - Connection state tracking
 *
 * @example
 * ```typescript
 * const parseEvent = useCallback((line: string) => {
 *   try {
 *     return JSON.parse(line) as MyEvent;
 *   } catch {
 *     return null;
 *   }
 * }, []);
 *
 * const handleEvent = useCallback((event: MyEvent) => {
 *   // Handle the event
 * }, []);
 *
 * const { isConnected, connectionError } = useSSEStream({
 *   url: '/api/stream',
 *   enabled: true,
 *   parseEvent,
 *   onEvent: handleEvent,
 * });
 * ```
 */
export function useSSEStream<TEvent>(options: SSEStreamOptions<TEvent>): SSEStreamReturn {
  const {
    url,
    method = "GET",
    body,
    enabled,
    parseEvent,
    onEvent,
    onComplete,
    onError,
    delimiter = "\n",
    reconnect: shouldReconnect = false,
    maxReconnectAttempts = 5,
  } = options;

  const [isConnected, setIsConnected] = useState(false);
  const [connectionError, setConnectionError] = useState<string | null>(null);

  // Refs for cleanup and reconnection
  const abortControllerRef = useRef<AbortController | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const isConnectingRef = useRef(false);

  // Cleanup helper
  const cleanup = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    isConnectingRef.current = false;
  }, []);

  const connect = useCallback(async () => {
    if (!enabled || isConnectingRef.current) return;

    // Cleanup previous connection
    cleanup();
    isConnectingRef.current = true;

    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      const response = await apiStream(url, {
        method,
        body: body ? JSON.stringify(body) : undefined,
        headers: { Accept: "text/event-stream" },
        signal: controller.signal,
      });

      if (!response.body) {
        throw new Error("No response body");
      }

      setIsConnected(true);
      setConnectionError(null);
      reconnectAttemptsRef.current = 0;
      isConnectingRef.current = false;

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split(delimiter);
        // Keep the last element as it may be incomplete
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (!line.trim()) continue;

          const event = parseEvent(line);
          if (event) {
            onEvent(event);
          }
        }
      }

      // Stream completed normally
      setIsConnected(false);
      onComplete?.();
    } catch (error) {
      isConnectingRef.current = false;

      // Abort error is expected on cleanup - don't report as error
      if ((error as Error).name === "AbortError") {
        return;
      }

      setIsConnected(false);
      const errorMessage = error instanceof Error ? error.message : "Connection failed";
      setConnectionError(errorMessage);

      // Handle reconnection with exponential backoff
      if (shouldReconnect && reconnectAttemptsRef.current < maxReconnectAttempts) {
        const delay = Math.min(1000 * Math.pow(2, reconnectAttemptsRef.current), 30000);
        reconnectAttemptsRef.current++;
        reconnectTimeoutRef.current = setTimeout(connect, delay);
      } else if (shouldReconnect) {
        onError?.("Max reconnection attempts reached");
      } else {
        onError?.(errorMessage);
      }
    }
  }, [
    enabled,
    url,
    method,
    body,
    delimiter,
    parseEvent,
    onEvent,
    onComplete,
    onError,
    shouldReconnect,
    maxReconnectAttempts,
    cleanup,
  ]);

  // Connect on mount/enable, cleanup on unmount/disable
  useEffect(() => {
    if (enabled) {
      connect();
    } else {
      cleanup();
      setIsConnected(false);
    }
    return cleanup;
  }, [enabled, connect, cleanup]);

  const disconnect = useCallback(() => {
    cleanup();
    setIsConnected(false);
  }, [cleanup]);

  const manualReconnect = useCallback(() => {
    reconnectAttemptsRef.current = 0;
    connect();
  }, [connect]);

  return {
    isConnected,
    connectionError,
    reconnect: manualReconnect,
    disconnect,
  };
}
