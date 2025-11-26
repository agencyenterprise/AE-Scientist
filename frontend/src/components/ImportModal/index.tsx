"use client";

import React, { useEffect, useRef, useState } from "react";

import { ModelSelector } from "@/components/ModelSelector";
import { PromptEditModal } from "@/components/ProjectDraft/PromptEditModal";
import { config } from "@/lib/config";
import { PromptTypes } from "@/lib/prompt-types";
import { ImportState, SSEConflict, SSEModelLimit, SSEProgress, SSEState } from "./types";
import { ConflictResolution } from "./ConflictResolution";
import { StreamingView } from "./StreamingView";

interface ImportModalProps {
  isOpen: boolean;
  onClose: () => void;
  isLoading?: boolean;
  onImportStart?: () => void;
  onImportEnd?: () => void;
}

const CHATGPT_URL_PATTERN =
  /^https:\/\/chatgpt\.com\/share\/[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/;
const BRANCHPROMPT_URL_PATTERN = /^https:\/\/v2\.branchprompt\.com\/conversation\/[a-f0-9]{24}$/;
const CLAUDE_URL_PATTERN =
  /^https:\/\/claude\.ai\/share\/[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/;
const GROK_URL_PATTERN = /^https:\/\/grok\.com\/share\//;

export function ImportModal({
  isOpen,
  onClose,
  isLoading = false,
  onImportStart,
  onImportEnd,
}: ImportModalProps) {
  const [url, setUrl] = useState("");
  const [error, setError] = useState("");
  const [isPromptModalOpen, setIsPromptModalOpen] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamingContent, setStreamingContent] = useState("");
  const [currentState, setCurrentState] = useState<ImportState | "">("");
  const [summaryProgress, setSummaryProgress] = useState<number | null>(null);
  const [selectedModel, setSelectedModel] = useState<string>("");
  const [selectedProvider, setSelectedProvider] = useState<string>("");
  const [currentModel, setCurrentModel] = useState<string>("");
  const [currentProvider, setCurrentProvider] = useState<string>("");
  const [hasConflict, setHasConflict] = useState(false);
  const [conflicts, setConflicts] = useState<
    Array<{ id: number; title: string; updated_at: string; url: string }>
  >([]);
  const [selectedConflictId, setSelectedConflictId] = useState<number | null>(null);
  const [isUpdateMode, setIsUpdateMode] = useState(false);
  const [hasModelLimitConflict, setHasModelLimitConflict] = useState(false);
  const [modelLimitMessage, setModelLimitMessage] = useState("");
  const [modelLimitSuggestion, setModelLimitSuggestion] = useState("");
  const streamingTextareaRef = useRef<HTMLTextAreaElement>(null);

  const handleClose = React.useCallback(() => {
    if (!isLoading && !isStreaming) {
      setUrl("");
      setError("");
      setStreamingContent("");
      setCurrentState("");
      setSelectedModel("");
      setSelectedProvider("");
      setHasConflict(false);
      setConflicts([]);
      setSelectedConflictId(null);
      setIsUpdateMode(false);
      setHasModelLimitConflict(false);
      setModelLimitMessage("");
      setModelLimitSuggestion("");
      onClose();
    }
  }, [isLoading, isStreaming, onClose]);

  const validateUrl = (u: string): boolean => {
    const s = u.trim();
    return (
      CHATGPT_URL_PATTERN.test(s) ||
      BRANCHPROMPT_URL_PATTERN.test(s) ||
      CLAUDE_URL_PATTERN.test(s) ||
      GROK_URL_PATTERN.test(s)
    );
  };

  const getStateMessage = (state: ImportState | ""): string => {
    if (isUpdateMode) {
      switch (state) {
        case "importing":
          return "Downloading updated conversation content...";
        case "summarizing":
          return summaryProgress !== null
            ? `Summarizing conversation (${summaryProgress}%)...`
            : "Summarizing conversation...";
        case "generating":
          return "Processing updates...";
        default:
          return "Updating conversation...";
      }
    } else {
      switch (state) {
        case "importing":
          return "Downloading shared conversation...";
        case "extracting_chat_keywords":
          return "Extracting chat keywords...";
        case "retrieving_memories":
          return "Retrieving memories...";
        case "summarizing":
          return summaryProgress !== null
            ? `Summarizing conversation (${summaryProgress}%)...`
            : "Summarizing conversation...";
        case "generating":
          return "Generating project draft...";
        default:
          return "Processing...";
      }
    }
  };

  const handleShowPromptModal = (): void => setIsPromptModalOpen(true);
  const handleClosePromptModal = (): void => setIsPromptModalOpen(false);

  const handleModelChange = (model: string, provider: string): void => {
    setError("");
    if (model && provider) {
      setSelectedModel(model);
      setSelectedProvider(provider);
      setCurrentModel(model);
      setCurrentProvider(provider);
    } else {
      setSelectedModel("");
      setSelectedProvider("");
    }
  };

  const handleModelDefaults = (model: string, provider: string): void => {
    if (!selectedModel && !selectedProvider) {
      setCurrentModel(model);
      setCurrentProvider(provider);
    }
  };

  const handleConflictRedirect = (): void => {
    if (selectedConflictId) {
      window.location.href = `/conversations/${selectedConflictId}`;
    }
  };

  const handleConflictUpdate = async (): Promise<void> => {
    setHasConflict(false);
    setConflicts([]);
    setSelectedConflictId(null);
    setError("");
    setIsStreaming(true);
    setIsUpdateMode(true);
    setStreamingContent("");
    setCurrentState("");
    onImportStart?.();
    try {
      await handleStreamingImport(url.trim(), "update_existing", selectedConflictId ?? undefined);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to import conversation");
      setIsStreaming(false);
      setIsUpdateMode(false);
    }
  };

  const handleConflictCancel = (): void => {
    setHasConflict(false);
    setConflicts([]);
    setSelectedConflictId(null);
    setError("");
  };

  const handleModelLimitProceed = async (): Promise<void> => {
    setHasModelLimitConflict(false);
    setError("");
    setIsStreaming(true);
    setIsUpdateMode(false);
    setStreamingContent("");
    setCurrentState("");
    onImportStart?.();
    try {
      await handleStreamingImport(url.trim(), "create_new", undefined, true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to import conversation");
      setIsStreaming(false);
    }
  };

  const handleModelLimitCancel = (): void => setHasModelLimitConflict(false);

  useEffect(() => {
    if (isStreaming && streamingTextareaRef.current) {
      const textarea = streamingTextareaRef.current;
      textarea.scrollTop = textarea.scrollHeight;
    }
  }, [streamingContent, isStreaming]);

  useEffect(() => {
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") handleClose();
    };
    if (isOpen) {
      document.addEventListener("keydown", handleEscape);
      return () => document.removeEventListener("keydown", handleEscape);
    }
    // When modal is closed, ensure streaming state resets so button is re-enabled next open
    setIsStreaming(false);
    return undefined;
  }, [isOpen, handleClose]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmedUrl = url.trim();
    if (!validateUrl(trimmedUrl)) {
      setError(
        "Invalid share URL. Expected ChatGPT https://chatgpt.com/share/{uuid}, BranchPrompt https://v2.branchprompt.com/conversation/{24-hex}, Claude https://claude.ai/share/{uuid}, or Grok https://grok.com/share/…"
      );
      return;
    }
    if (!currentModel || !currentProvider) {
      setError("LLM model and provider are required. Please wait for model to load.");
      return;
    }
    setError("");
    setIsStreaming(true);
    setIsUpdateMode(false);
    setStreamingContent("");
    setCurrentState("");
    onImportStart?.();
    try {
      await handleStreamingImport(trimmedUrl, "prompt");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to import conversation");
      setIsStreaming(false);
      onImportEnd?.();
    }
  };

  const handleStreamingImport = async (
    trimmedUrl: string,
    duplicateResolution: "prompt" | "update_existing" | "create_new",
    targetConversationId?: number,
    acceptSummarization: boolean = false
  ): Promise<void> => {
    const body =
      targetConversationId !== undefined
        ? {
            url: trimmedUrl,
            llm_model: currentModel,
            llm_provider: currentProvider,
            accept_summarization: acceptSummarization,
            duplicate_resolution: duplicateResolution,
            target_conversation_id: targetConversationId,
          }
        : {
            url: trimmedUrl,
            llm_model: currentModel,
            llm_provider: currentProvider,
            accept_summarization: acceptSummarization,
            duplicate_resolution: duplicateResolution,
          };

    const response = await fetch(`${config.apiUrl}/conversations/import`, {
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
        type SSEEvent = import("./types").SSEEvent;
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
            if (stateValue !== "summarizing") setSummaryProgress(null);
            break;
          }
          case "progress": {
            const prog = (eventData as SSEProgress).data;
            if (prog.phase === "summarizing" && prog.total > 0) {
              const pct = Math.max(0, Math.min(100, Math.round((prog.current / prog.total) * 100)));
              setSummaryProgress(pct);
              setCurrentState(ImportState.Summarizing);
            }
            break;
          }
          case "conflict": {
            setIsStreaming(false);
            setCurrentState("");
            const conflictEvt = eventData as SSEConflict;
            const items = conflictEvt.data.conversations;
            setConflicts(items);
            let selectedId: number | null = null;
            const firstItem = items[0];
            if (firstItem) {
              selectedId = firstItem.id;
            }
            setSelectedConflictId(selectedId);
            setHasConflict(true);
            onImportEnd?.();
            return;
          }
          case "model_limit_conflict": {
            setIsStreaming(false);
            setCurrentState("");
            const mdlEvt = eventData as SSEModelLimit;
            setModelLimitMessage(mdlEvt.data.message);
            setModelLimitSuggestion(mdlEvt.data.suggestion);
            setHasModelLimitConflict(true);
            onImportEnd?.();
            return;
          }
          case "error": {
            const err = eventData as { type: "error"; data: string; code?: string };
            // End streaming state and notify parent before throwing
            setIsStreaming(false);
            onImportEnd?.();
            if (err.code === "CHAT_NOT_FOUND") {
              throw new Error(
                "This conversation no longer exists or has been deleted. Please check the URL and try again."
              );
            }
            throw new Error(err.data);
          }
          case "done": {
            const done = eventData as {
              type: "done";
              data: { conversation?: { id: number }; error?: string };
            };
            const conv = done.data.conversation;
            if (conv && typeof conv.id === "number") {
              setUrl("");
              setIsStreaming(false);
              setIsUpdateMode(false);
              setCurrentState("");
              onImportEnd?.();
              onClose();
              window.location.href = `/conversations/${conv.id}`;
              return;
            }
            const err = done.data.error ?? "Import failed";
            throw new Error(err);
          }
          default:
            break;
        }
      }
    }
  };

  if (!isOpen) return null;

  return (
    <>
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black bg-opacity-50">
        <div
          className={`relative bg-card rounded-lg shadow-xl w-full max-h-[90vh] overflow-auto ${
            isStreaming ? "max-w-3xl" : "max-w-2xl"
          }`}
        >
          {hasConflict ? (
            <ConflictResolution
              conflicts={conflicts}
              selectedConflictId={selectedConflictId}
              onSelectConflict={setSelectedConflictId}
              onGoToSelected={handleConflictRedirect}
              onUpdateSelected={handleConflictUpdate}
              onCreateNew={async () => {
                setHasConflict(false);
                setConflicts([]);
                setSelectedConflictId(null);
                setError("");
                setIsStreaming(true);
                setIsUpdateMode(false);
                setStreamingContent("");
                setCurrentState("");
                onImportStart?.();
                try {
                  await handleStreamingImport(url.trim(), "create_new");
                } catch (err) {
                  setError(err instanceof Error ? err.message : "Failed to import conversation");
                  setIsStreaming(false);
                }
              }}
              onCancel={handleConflictCancel}
              onClose={handleClose}
            />
          ) : hasModelLimitConflict ? (
            <div className="p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-medium text-foreground">Conversation Too Large</h3>
                <button
                  type="button"
                  onClick={handleClose}
                  className="text-muted-foreground hover:text-foreground p-1 rounded"
                >
                  <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M6 18L18 6M6 6l12 12"
                    />
                  </svg>
                </button>
              </div>

              <div className="mb-6 space-y-3">
                <p className="text-foreground">{modelLimitMessage}</p>
                <p className="text-muted-foreground">{modelLimitSuggestion}</p>
                <p className="text-sm text-muted-foreground">
                  Note: Summarization can take several minutes.
                </p>
              </div>

              <div className="space-y-3 mb-6">
                <button
                  onClick={handleModelLimitProceed}
                  className="w-full p-4 text-left border border-border rounded-lg hover:bg-muted focus:outline-none focus:ring-2 focus:ring-ring"
                >
                  <div className="font-medium text-foreground">Proceed with summarization</div>
                  <div className="text-sm text-muted-foreground">
                    We&apos;ll create a placeholder and update it when ready
                  </div>
                </button>

                <button
                  onClick={handleModelLimitCancel}
                  className="w-full p-4 text-left border border-border rounded-lg hover:bg-muted focus:outline-none focus:ring-2 focus:ring-ring"
                >
                  <div className="font-medium text-foreground">Choose another model</div>
                  <div className="text-sm text-muted-foreground">
                    Select a model with a larger context window
                  </div>
                </button>
              </div>
            </div>
          ) : isStreaming ? (
            <StreamingView
              isUpdateMode={isUpdateMode}
              streamingContent={streamingContent}
              currentState={currentState}
              summaryProgress={summaryProgress}
              onClose={handleClose}
              getStateMessage={getStateMessage}
              textareaRef={streamingTextareaRef}
            />
          ) : (
            <form onSubmit={handleSubmit}>
              <div className="p-6">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-lg font-medium text-foreground">Import Conversation</h3>
                  <div className="flex items-center space-x-2">
                    <ModelSelector
                      promptType={PromptTypes.IDEA_GENERATION}
                      onModelChange={handleModelChange}
                      onDefaultsChange={handleModelDefaults}
                      selectedModel={selectedModel}
                      selectedProvider={selectedProvider}
                      disabled={isLoading || isStreaming}
                      showMakeDefault={true}
                      showCapabilities={false}
                    />
                    <button
                      type="button"
                      onClick={handleShowPromptModal}
                      disabled={isLoading || isStreaming}
                      className="btn-secondary text-xs py-1 px-2 disabled:opacity-50"
                      title="Configure project generation prompt"
                    >
                      <span>⚙️</span>
                      <span className="ml-1">LLM Prompt</span>
                    </button>
                    <button
                      type="button"
                      onClick={handleClose}
                      disabled={isLoading || isStreaming}
                      className="text-muted-foreground hover:text-foreground disabled:opacity-50 p-1 rounded"
                    >
                      <svg
                        className="w-6 h-6"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M6 18L18 6M6 6l12 12"
                        />
                      </svg>
                    </button>
                  </div>
                </div>

                <div className="mb-4">
                  <label htmlFor="url" className="block text-sm font-medium text-muted-foreground mb-2">
                    Share URL
                  </label>
                  <input
                    type="url"
                    id="url"
                    value={url}
                    onChange={e => setUrl(e.target.value)}
                    disabled={isLoading || isStreaming || !currentModel}
                    placeholder={"Paste a share URL from ChatGPT, BranchPrompt, Claude, or Grok"}
                    className="input-field"
                  />
                  <p className="mt-2 text-sm text-muted-foreground">
                    Paste a ChatGPT, BranchPrompt, Claude, or Grok conversation share URL.
                  </p>
                </div>

                {error && (
                  <div className="mb-4 p-3 bg-destructive/10 border border-destructive/30 rounded-md">
                    <p className="text-sm text-destructive">{error}</p>
                  </div>
                )}

                <div className="mb-4 p-3 bg-muted rounded-md">
                  <p className="text-sm text-muted-foreground">
                    <strong>Example:</strong>
                  </p>
                  <div className="text-xs text-muted-foreground font-mono mt-1 break-all space-y-1">
                    <p>https://chatgpt.com/share/12345678-1234-1234-1234-123456789abc</p>
                    <p>https://v2.branchprompt.com/conversation/67fe0326915f8dd81a3b1f74</p>
                    <p>https://claude.ai/share/12a33e29-2225-4d45-bae1-416a8647794d</p>
                    <p>https://grok.com/share/abc_1234-5678-90ab-cdef-1234567890ab</p>
                  </div>
                </div>
              </div>

              <div className="bg-muted px-6 py-3 flex flex-row-reverse gap-3">
                <button
                  type="submit"
                  disabled={isLoading || isStreaming || !url.trim() || !currentModel}
                  className="btn-primary-gradient px-4 py-2 disabled:bg-muted disabled:text-muted-foreground disabled:cursor-not-allowed disabled:shadow-none"
                >
                  {isLoading || isStreaming ? (
                    <>
                      <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                      Importing...
                    </>
                  ) : (
                    "Import Conversation"
                  )}
                </button>
                <button
                  type="button"
                  onClick={handleClose}
                  disabled={isLoading || isStreaming}
                  className="btn-secondary disabled:opacity-50"
                >
                  Cancel
                </button>
              </div>
            </form>
          )}
        </div>
      </div>

      <PromptEditModal
        isOpen={isPromptModalOpen}
        onClose={handleClosePromptModal}
        promptType={PromptTypes.IDEA_GENERATION}
      />
    </>
  );
}

export default ImportModal;
