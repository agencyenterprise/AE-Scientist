"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { ImportState } from "@/features/conversation-import/types/types";
import type { SSEEvent } from "@/features/conversation-import/types/types";
import { apiStream } from "@/shared/lib/api-client";

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

const SECTION_ORDER = [
  "title",
  "short_hypothesis",
  "related_work",
  "abstract",
  "experiments",
  "expected_outcome",
  "risk_factors_and_limitations",
] as const;

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

        const response = await apiStream("/conversations/import/manual", {
          method: "POST",
          headers: { Accept: "text/event-stream" },
          body: JSON.stringify(body),
        });

        if (!response.body) throw new Error("No response body");

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let accumulatedContent = "";
        const sectionMap: Record<string, string> = {};
        const buildSectionContent = () =>
          SECTION_ORDER.filter(key => sectionMap[key])
            .map(key => sectionMap[key])
            .join("\n");
        const updateStreamingContent = () => {
          const sectionContent = buildSectionContent();
          setStreamingContent(sectionContent || accumulatedContent);
        };
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
              eventData = JSON.parse(line) as SSEEvent;
            } catch (e) {
              // eslint-disable-next-line no-console
              console.warn("Failed to parse JSON line:", line, "Error:", e);
              continue;
            }

            switch (eventData.type) {
              case "content": {
                accumulatedContent += eventData.data;
                updateStreamingContent();
                break;
              }
              case "section_update": {
                const { field, data } = eventData;
                sectionMap[field] = data;
                updateStreamingContent();
                break;
              }
              case "state": {
                setCurrentState(eventData.data as ImportState);
                break;
              }
              case "progress": {
                if (eventData.data.phase === "summarizing" && eventData.data.total > 0) {
                  setCurrentState(ImportState.Summarizing);
                }
                break;
              }
              case "error": {
                setIsStreaming(false);
                onImportEnd?.();
                throw new Error(eventData.data);
              }
              case "model_limit_conflict": {
                const message = eventData.data.message;
                setIsStreaming(false);
                setError(message);
                onImportEnd?.();
                onError?.(message);
                return;
              }
              case "done": {
                const conversation = eventData.data.conversation;
                if (conversation && typeof conversation.id === "number") {
                  setIsStreaming(false);
                  setCurrentState("");
                  onImportEnd?.();
                  onSuccess?.(conversation.id);
                  if (autoRedirect) {
                    window.location.href = `/conversations/${conversation.id}`;
                  }
                  return;
                }
                const errMsg = eventData.data.error ?? "Import failed";
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
