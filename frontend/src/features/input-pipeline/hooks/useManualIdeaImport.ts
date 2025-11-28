"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import {
  ImportState,
  SSEEvent,
  SSEProgress,
  SSEState,
} from "@/features/conversation-import/types/types";
import { config } from "@/shared/lib/config";

export interface UseManualIdeaImportOptions {
  onImportStart?: () => void;
  onImportEnd?: () => void;
  onSuccess?: (conversationId: number) => void;
  onError?: (error: string) => void;
  autoRedirect?: boolean;
}

export interface UseManualIdeaImportReturn {
  state: {
    error: string;
    streamingContent: string;
    currentState: ImportState | "";
  };
  status: {
    isIdle: boolean;
    isImporting: boolean;
    hasError: boolean;
  };
  actions: {
    startImport: (title: string, idea: string, model: string, provider: string) => Promise<void>;
    reset: () => void;
  };
  streamingRef: React.RefObject<HTMLTextAreaElement | null>;
}

export function useManualIdeaImport(
  options: UseManualIdeaImportOptions = {}
): UseManualIdeaImportReturn {
  const { onImportStart, onImportEnd, onSuccess, onError, autoRedirect = true } = options;

  // Streaming state
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamingContent, setStreamingContent] = useState("");
  const [currentState, setCurrentState] = useState<ImportState | "">("");
  const [error, setError] = useState("");

  // Ref for auto-scrolling
  const streamingRef = useRef<HTMLTextAreaElement>(null);

  // Auto-scroll streaming content
  useEffect(() => {
    if (isStreaming && streamingRef.current) {
      streamingRef.current.scrollTop = streamingRef.current.scrollHeight;
    }
  }, [streamingContent, isStreaming]);

  // Reset all state
  const reset = useCallback(() => {
    setError("");
    setStreamingContent("");
    setCurrentState("");
    setIsStreaming(false);
  }, []);

  // Start import action
  const startImport = useCallback(
    async (title: string, idea: string, model: string, provider: string) => {
      if (!title.trim() || !idea.trim()) {
        const validationError = "Title and hypothesis are required";
        setError(validationError);
        onError?.(validationError);
        return;
      }

      if (!model || !provider) {
        const modelError = "LLM model and provider are required. Please wait for model to load.";
        setError(modelError);
        onError?.(modelError);
        return;
      }

      setError("");
      setIsStreaming(true);
      setStreamingContent("");
      setCurrentState("");
      onImportStart?.();

      try {
        const body = {
          idea_title: title.trim(),
          idea_hypothesis: idea.trim(),
          llm_model: model,
          llm_provider: provider,
        };

        const response = await fetch(`${config.apiUrl}/conversations/import/manual`, {
          method: "POST",
          credentials: "include",
          headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
          body: JSON.stringify(body),
        });

        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        if (!response.body) throw new Error("No response body");

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let accumulatedContent = "";
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() || "";

          for (const line of lines) {
            if (!line.trim()) continue;

            let eventData: SSEEvent;
            try {
              eventData = JSON.parse(line);
            } catch (e) {
              // eslint-disable-next-line no-console
              console.warn("Failed to parse JSON line:", line, "Error:", e);
              continue;
            }

            switch (eventData.type) {
              case "content": {
                const content = (eventData as { type: "content"; data: string }).data;
                accumulatedContent += content;
                setStreamingContent(accumulatedContent);
                break;
              }
              case "state": {
                const stateValue = (eventData as SSEState).data;
                setCurrentState(stateValue);
                break;
              }
              case "progress": {
                const prog = (eventData as SSEProgress).data;
                if (prog.phase === "summarizing" && prog.total > 0) {
                  setCurrentState(ImportState.Summarizing);
                }
                break;
              }
              case "error": {
                const err = eventData as { type: "error"; data: string; code?: string };
                setIsStreaming(false);
                onImportEnd?.();
                throw new Error(err.data);
              }
              case "done": {
                const doneEvt = eventData as {
                  type: "done";
                  data: { conversation?: { id: number }; error?: string };
                };
                const conv = doneEvt.data.conversation;
                if (conv && typeof conv.id === "number") {
                  setIsStreaming(false);
                  setCurrentState("");
                  onImportEnd?.();
                  onSuccess?.(conv.id);
                  if (autoRedirect) {
                    window.location.href = `/conversations/${conv.id}`;
                  }
                  return;
                }
                const errMsg = doneEvt.data.error ?? "Import failed";
                throw new Error(errMsg);
              }
              default:
                break;
            }
          }
        }
      } catch (err) {
        const errorMessage = err instanceof Error ? err.message : "Failed to generate idea";
        setError(errorMessage);
        setIsStreaming(false);
        onImportEnd?.();
        onError?.(errorMessage);
      }
    },
    [onImportStart, onImportEnd, onSuccess, onError, autoRedirect]
  );

  return {
    state: {
      error,
      streamingContent,
      currentState,
    },
    status: {
      isIdle: !isStreaming,
      isImporting: isStreaming,
      hasError: !!error,
    },
    actions: {
      startImport,
      reset,
    },
    streamingRef,
  };
}
