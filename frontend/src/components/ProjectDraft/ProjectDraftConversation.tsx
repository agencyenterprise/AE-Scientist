"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";

import { FileAttachmentList } from "@/components/FileAttachment";
import { FileUpload } from "@/components/FileUpload";
import { ModelSelector } from "@/components/ModelSelector";
import { config } from "@/lib/config";
import { PromptTypes } from "@/lib/prompt-types";
import type { ChatMessage, ChatRequest, FileAttachment, Idea, FileMetadata } from "@/types";
import { isErrorResponse } from "@/lib/api-adapters";
import { ChatStatus } from "@/types";
import { isIdeaGenerating } from "./utils/versionUtils";
import { useAuth } from "@/hooks/useAuth";

interface ProjectDraftConversationProps {
  conversationId: number;
  isLocked: boolean;
  currentProjectDraft?: Idea | null;
  onProjectDraftUpdate?: (updatedDraft: Idea) => void;
  onOpenPromptModal?: () => void;
  onConversationLocked?: () => void;
  conversationCapabilities?: {
    hasImages?: boolean;
    hasPdfs?: boolean;
  };
  isVisible: boolean;
}

// Type-safe status message mapping with compile-time completeness check
const STATUS_MESSAGES: Record<ChatStatus, string> = {
  [ChatStatus.ANALYZING_REQUEST]: "🔄 Analyzing your request...",
  [ChatStatus.EXECUTING_TOOLS]: "🔧 Processing...",
  [ChatStatus.GETTING_IDEA]: "📄 Getting current idea...",
  [ChatStatus.UPDATING_IDEA]: "📝 Updating idea...",
  [ChatStatus.GENERATING_RESPONSE]: "🤔 Generating response...",
  [ChatStatus.DONE]: "",
};

// Reusable markdown component for chat messages
function ChatMarkdown({
  content,
  isUser,
  attachments = [],
}: {
  content: string;
  isUser: boolean;
  attachments?: FileAttachment[];
}) {
  // Preprocess content to preserve line breaks in chat messages
  // Add two spaces before each line break to create proper markdown line breaks
  const processedContent = content.replace(/\n/g, "  \n");

  return (
    <div>
      <ReactMarkdown
        className={`prose prose-sm ${isUser ? "prose-invert" : ""}`}
        components={{
          h1: ({ children }) => (
            <h1 className="text-base font-bold mb-1 mt-2 first:mt-0">{children}</h1>
          ),
          h2: ({ children }) => (
            <h2 className="text-sm font-semibold mb-1 mt-2 first:mt-0">{children}</h2>
          ),
          h3: ({ children }) => (
            <h3 className="text-sm font-medium mb-1 mt-1 first:mt-0">{children}</h3>
          ),
          p: ({ children }) => <p className="mb-1 last:mb-0">{children}</p>,
          ul: ({ children }) => <ul className="list-disc ml-4 mb-1 space-y-0.5">{children}</ul>,
          ol: ({ children }) => <ol className="list-decimal ml-4 mb-1 space-y-0.5">{children}</ol>,
          li: ({ children }) => <li className="text-sm">{children}</li>,
          code: ({ children }) => (
            <code
              className={`px-1 py-0.5 rounded text-xs font-mono ${
                isUser ? "bg-primary/30" : "bg-muted"
              }`}
            >
              {children}
            </code>
          ),
          pre: ({ children }) => (
            <pre
              className={`p-2 rounded text-xs font-mono mb-1 whitespace-pre-wrap break-all max-w-full ${
                isUser ? "bg-primary/30" : "bg-muted"
              }`}
              style={{ width: "100%", maxWidth: "100%", overflowWrap: "anywhere" }}
            >
              {children}
            </pre>
          ),
          strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
          em: ({ children }) => <em className="italic">{children}</em>,
          a: ({ href, children }) => (
            <a
              href={href}
              className={`hover:underline ${isUser ? "text-primary/80" : "text-primary"}`}
              target="_blank"
              rel="noopener noreferrer"
            >
              {children}
            </a>
          ),
          blockquote: ({ children }) => (
            <blockquote
              className={`border-l-2 pl-2 my-1 ${isUser ? "border-primary/50" : "border-border"}`}
            >
              {children}
            </blockquote>
          ),
        }}
      >
        {processedContent}
      </ReactMarkdown>

      {/* Render file attachments */}
      {attachments.length > 0 && (
        <div className={`mt-2 ${isUser ? "text-white" : ""}`}>
          <FileAttachmentList attachments={attachments} showPreviews={true} maxItems={3} />
        </div>
      )}
    </div>
  );
}

// Type guard function to check if a string is a valid ChatStatus
function isChatStatus(value: string): value is ChatStatus {
  return Object.values(ChatStatus).includes(value as ChatStatus);
}

export function ProjectDraftConversation({
  conversationId,
  isLocked,
  currentProjectDraft,
  // project is passed by parent but not used here anymore (banner moved to parent)
  onProjectDraftUpdate,
  onOpenPromptModal,
  onConversationLocked,
  conversationCapabilities,
  isVisible,
}: ProjectDraftConversationProps) {
  const { user } = useAuth();

  // Ensure user is authenticated for chat functionality
  if (!user) {
    throw new Error("User must be authenticated to use chat functionality");
  }
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputMessage, setInputMessage] = useState("");
  const [isLoadingHistory, setIsLoadingHistory] = useState(true);
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamingContent, setStreamingContent] = useState("");
  const [statusMessage, setStatusMessage] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [selectedModel, setSelectedModel] = useState<string>("");
  const [selectedProvider, setSelectedProvider] = useState<string>("");
  const [currentModel, setCurrentModel] = useState<string>("");
  const [currentProvider, setCurrentProvider] = useState<string>("");
  const [modelCapabilities, setModelCapabilities] = useState<{
    supportsImages: boolean;
    supportsPdfs: boolean;
  }>({ supportsImages: false, supportsPdfs: false });
  const [pendingFiles, setPendingFiles] = useState<FileMetadata[]>([]);
  const [showFileUpload, setShowFileUpload] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const eventSourceRef = useRef<EventSource | null>(null);

  // Check if project draft is currently being generated
  const isGenerating = isIdeaGenerating(currentProjectDraft || null);
  const isReadOnly = isLocked || isGenerating;

  // Compute effective capabilities by merging conversation capabilities with current session uploads
  const effectiveCapabilities = useMemo(() => {
    // Check if there are any images in pending files
    const hasUploadedImages = pendingFiles.some(file => file.file_type.startsWith("image/"));

    // Check if there are any PDFs in pending files
    const hasUploadedPdfs = pendingFiles.some(file => file.file_type === "application/pdf");

    // Check if there are any images in sent messages during this session
    const hasSentImages = messages.some(message =>
      message.attachments?.some(attachment => attachment.file_type.startsWith("image/"))
    );

    // Check if there are any PDFs in sent messages during this session
    const hasSentPdfs = messages.some(message =>
      message.attachments?.some(attachment => attachment.file_type === "application/pdf")
    );

    return {
      hasImages: conversationCapabilities?.hasImages || hasUploadedImages || hasSentImages,
      hasPdfs: conversationCapabilities?.hasPdfs || hasUploadedPdfs || hasSentPdfs,
    };
  }, [conversationCapabilities, pendingFiles, messages]);

  // Auto-scroll to bottom when new messages arrive
  const scrollToBottom = (): void => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  // Cleanup EventSource on unmount
  useEffect(() => {
    const currentEventSource = eventSourceRef.current;
    return () => {
      if (currentEventSource) {
        currentEventSource.close();
      }
    };
  }, []);

  // Load chat history when conversation changes
  useEffect(() => {
    const loadChatHistory = async (): Promise<void> => {
      setIsLoadingHistory(true);
      setError(null);

      try {
        const response = await fetch(`${config.apiUrl}/conversations/${conversationId}/idea/chat`, {
          method: "GET",
          credentials: "include",
        });

        if (response.ok) {
          const result = await response.json();
          if (isErrorResponse(result)) {
            // eslint-disable-next-line no-console
            console.warn("Failed to load chat history:", result.error);
            setMessages([]); // Start with empty if there's an issue
          } else {
            setMessages(result.chat_messages || []);
          }
        } else {
          // If conversation/project draft doesn't exist yet, start with empty chat
          setMessages([]);
        }
      } catch (err) {
        // eslint-disable-next-line no-console
        console.warn("Failed to load chat history:", err);
        setMessages([]); // Start with empty if there's an issue
      } finally {
        setIsLoadingHistory(false);
      }
    };

    loadChatHistory();
  }, [conversationId]);

  useEffect(() => {
    scrollToBottom();
  }, [messages, streamingContent]);

  // When chat becomes visible (e.g., mobile toggle), ensure we scroll to the latest message
  useEffect(() => {
    let timeoutId: number | null = null;
    if (isVisible) {
      // wait for layout to update after visibility change
      timeoutId = window.setTimeout(() => {
        scrollToBottom();
      }, 0);
    }
    return () => {
      if (timeoutId !== null) {
        clearTimeout(timeoutId);
      }
    };
  }, [isVisible]);

  // Model capabilities are managed by ModelSelector via handleCapabilitiesChange callback

  const handleModelChange = (model: string, provider: string): void => {
    // Update both selected (for custom selections) and current (for sending requests)
    if (model && provider) {
      // User made a custom selection
      setSelectedModel(model);
      setSelectedProvider(provider);
      setCurrentModel(model);
      setCurrentProvider(provider);
    } else {
      // User cleared custom selection, will use defaults
      setSelectedModel("");
      setSelectedProvider("");
      // currentModel/currentProvider will be set by ModelSelector when defaults load
    }
  };

  const handleModelDefaults = (model: string, provider: string): void => {
    // Called by ModelSelector when defaults are loaded or when selection falls back to defaults
    if (!selectedModel && !selectedProvider) {
      // Only update current if no custom selection
      setCurrentModel(model);
      setCurrentProvider(provider);
    }
  };

  const handleModelCapabilities = (capabilities: {
    supportsImages: boolean;
    supportsPdfs: boolean;
  }): void => {
    setModelCapabilities(capabilities);
  };

  const sendMessage = async (): Promise<void> => {
    if (!inputMessage.trim() || isStreaming) return;

    // Use the current model and provider (set by ModelSelector)
    if (!currentModel || !currentProvider) {
      setError("LLM model and provider are required. Please wait for model to load.");
      return;
    }

    const userMessage = inputMessage.trim();
    // Collect attachment IDs from uploaded files
    const attachmentIds: number[] = pendingFiles.map(file => file.id);

    setInputMessage("");
    setError(null);
    setIsStreaming(true);
    setStreamingContent("");
    setStatusMessage("🔄 Sending message...");

    // Clear pending files after sending
    const currentFiles = [...pendingFiles];
    setPendingFiles([]);
    setShowFileUpload(false);

    // Reset textarea height when sending message
    if (inputRef.current) {
      inputRef.current.style.height = "auto";
    }

    // Convert pending files to attachments format
    const messageAttachments: FileAttachment[] = currentFiles.map(file => ({
      id: file.id,
      filename: file.filename,
      file_size: file.file_size,
      file_type: file.file_type,
      s3_key: file.s3_key,
      created_at: new Date().toISOString(),
    }));

    // Optimistically add user message
    const optimisticUserMessage: ChatMessage = {
      role: "user",
      content: userMessage,
      sequence_number: messages.length + 1,
      created_at: new Date().toISOString(),
      sent_by_user_id: user.id,
      sent_by_user_name: user.name,
      sent_by_user_email: user.email,
      attachments: messageAttachments,
    };
    setMessages(prev => [...prev, optimisticUserMessage]);

    // Setup timeout for streaming connection
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 300000); // 5 minute timeout

    try {
      // Use fetch for streaming POST request with timeout

      const response = await fetch(
        `${config.apiUrl}/conversations/${conversationId}/idea/chat/stream`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Accept: "text/event-stream",
          },
          credentials: "include",
          body: JSON.stringify({
            message: userMessage,
            llm_model: currentModel,
            llm_provider: currentProvider,
            attachment_ids: attachmentIds,
          } as ChatRequest),
          signal: controller.signal,
        }
      );

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      if (!response.body) {
        throw new Error("No response body");
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();

      let accumulatedContent = "";
      let projectUpdated = false;
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || ""; // Keep incomplete line in buffer

        for (const line of lines) {
          if (!line.trim()) continue;

          try {
            const eventData = JSON.parse(line);
            const eventType = eventData.type;
            const data = eventData.data;

            // Handle different event types
            if (eventType === "status") {
              const statusValue = typeof data === "string" ? data : String(data);

              // Type-safe status handling with runtime validation
              if (isChatStatus(statusValue)) {
                const displayMessage = STATUS_MESSAGES[statusValue];
                setStatusMessage(displayMessage);
              } else {
                // eslint-disable-next-line no-console
                console.warn(`Unknown status value received: ${statusValue}`);
                setStatusMessage(""); // Clear status on unknown value
              }
            } else if (eventType === "content") {
              const content = typeof data === "string" ? data : String(data);
              accumulatedContent += content;

              setStreamingContent(accumulatedContent);
            } else if (eventType === "idea_updated") {
              projectUpdated = true;
              setStatusMessage("📝 Idea updated!");
            } else if (eventType === "conversation_locked") {
              setStatusMessage("🔒 Project created successfully!");
              // Notify parent component that conversation is locked
              if (onConversationLocked) {
                onConversationLocked();
              }
            } else if (eventType === "error") {
              const errorMsg = typeof data === "string" ? data : String(data);

              throw new Error(errorMsg);
            } else if (eventType === "done") {
              break;
            }
          } catch (parseError) {
            // eslint-disable-next-line no-console
            console.warn("Failed to parse JSON line:", line, "Error:", parseError);
          }
        }
      }

      // Add the final assistant message if we have content
      if (accumulatedContent.trim()) {
        const assistantMessage: ChatMessage = {
          role: "assistant",
          content: accumulatedContent.trim(),
          sequence_number: messages.length + 2,
          created_at: new Date().toISOString(),
          sent_by_user_id: user.id, // User who triggered this response
          sent_by_user_name: user.name,
          sent_by_user_email: user.email,
          attachments: [],
        };

        setMessages(prev => [...prev, assistantMessage]);
      }

      // Trigger idea update if needed
      if (projectUpdated && onProjectDraftUpdate) {
        // Fetch the latest idea data
        try {
          const response = await fetch(`${config.apiUrl}/conversations/${conversationId}/idea`, {
            credentials: "include",
          });
          if (response.ok) {
            const result = await response.json();
            if (!isErrorResponse(result) && result.idea) {
              onProjectDraftUpdate(result.idea);
            }
          }
        } catch (err) {
          // eslint-disable-next-line no-console
          console.error("Failed to fetch updated idea:", err);
        }
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : "Failed to send message";
      setError(errorMessage);
      // eslint-disable-next-line no-console
      console.error("Streaming error:", err);

      // Remove optimistic message on error and restore files
      setMessages(prev => prev.slice(0, -1));
      setPendingFiles(currentFiles);
    } finally {
      // Always clear timeout
      clearTimeout(timeoutId);
      setIsStreaming(false);
      setStreamingContent("");
      setStatusMessage("");

      // Focus input field when response is complete and reset height
      // Use setTimeout to ensure state updates are applied first
      setTimeout(() => {
        if (inputRef.current) {
          inputRef.current.focus();
          inputRef.current.style.height = "auto";
        }
      }, 100);
    }
  };

  const handleKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>): void => {
    if (
      event.key === "Enter" &&
      !event.shiftKey &&
      !event.metaKey &&
      !event.ctrlKey &&
      !isStreaming
    ) {
      event.preventDefault();
      sendMessage();
    }
    // Cmd+Return or Ctrl+Return allows line breaks
    // Shift+Enter also allows line breaks (default textarea behavior)
  };

  const handleFilesUploaded = (files: FileMetadata[]) => {
    setPendingFiles(prev => [...prev, ...files]);
  };

  const removePendingFile = (s3Key: string) => {
    setPendingFiles(prev => prev.filter(file => file.s3_key !== s3Key));
  };

  const formatTimestamp = (timestamp: string): string => {
    return new Date(timestamp).toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  return (
    <div className="flex flex-col h-full bg-card max-w-full overflow-x-hidden">
      {/* Chat Header with Configure AI */}
      <div className="flex-shrink-0 px-4 pt-2 pb-1 border-b border-border bg-gradient-to-r from-muted to-muted/80">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-2">
          <div className="flex items-center space-x-2">
            <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
            <div className="flex flex-row md:flex-col items-baseline gap-1">
              <h3 className="text-sm font-medium text-foreground">Project Chat</h3>
              <span className="text-xs text-muted-foreground">Discuss and refine with AI</span>
            </div>
          </div>
          <div className="flex items-center space-x-2 md:mt-0 mt-1">
            <ModelSelector
              promptType={PromptTypes.IDEA_CHAT}
              onModelChange={handleModelChange}
              onDefaultsChange={handleModelDefaults}
              onCapabilitiesChange={handleModelCapabilities}
              selectedModel={selectedModel}
              selectedProvider={selectedProvider}
              disabled={isReadOnly || isStreaming}
              showMakeDefault={true}
              conversationCapabilities={effectiveCapabilities}
            />
            {onOpenPromptModal && !isReadOnly && (
              <button
                onClick={onOpenPromptModal}
                className="flex items-center space-x-1 px-2 py-1 text-xs font-medium text-[var(--primary-700)] hover:bg-[var(--muted)] rounded border border-[var(--border)] transition-colors"
                title="Configure AI prompts"
              >
                <span>⚙️</span>
                <span>AI Config</span>
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Messages Area */}
      <div
        className={`flex-1 overflow-y-auto px-4 py-4 ${messages.length > 0 || isStreaming ? "space-y-4" : ""} min-h-0 max-w-full overflow-x-hidden`}
      >
        {isLoadingHistory ? (
          <div className="text-center text-muted-foreground mt-8">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[var(--primary)] mx-auto mb-2"></div>
            <p className="text-sm">Loading chat history...</p>
          </div>
        ) : messages.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-center text-muted-foreground">
            <svg
              className="mx-auto h-12 w-12 text-muted-foreground/60 mb-4"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
              />
            </svg>
            <p className="text-lg font-medium">Start a conversation</p>
            <p className="text-sm mt-1">Ask questions about your project or request improvements</p>
          </div>
        ) : (
          messages.map((message, index) => (
            <div
              key={`${message.sequence_number}-${index}`}
              className={`flex ${message.role === "user" ? "justify-end" : "justify-start"} overflow-hidden`}
            >
              <div
                className={`max-w-[80%] min-w-0 rounded-lg px-4 py-2 break-words overflow-hidden ${
                  message.role === "user"
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted text-foreground border border-border"
                }`}
              >
                <ChatMarkdown
                  content={message.content}
                  isUser={message.role === "user"}
                  attachments={message.attachments}
                />
                <div
                  className={`text-xs mt-1 flex items-center space-x-2 ${
                    message.role === "user" ? "text-primary-foreground/70" : "text-muted-foreground"
                  }`}
                >
                  <span>{message.role === "user" ? message.sent_by_user_name : "Assistant"}</span>
                  <span>•</span>
                  <span>{formatTimestamp(message.created_at)}</span>
                </div>
              </div>
            </div>
          ))
        )}

        {/* Streaming content */}
        {isStreaming && (
          <div className="flex items-start space-x-3">
            <div className="flex-shrink-0 w-8 h-8 bg-primary rounded-full flex items-center justify-center text-primary-foreground text-sm font-medium">
              AI
            </div>
            <div className="flex-1 bg-muted rounded-lg px-4 py-2 max-w-3xl min-w-0 break-words overflow-hidden">
              {statusMessage && (
                <div className="text-sm text-muted-foreground mb-2 font-medium flex items-center space-x-2">
                  {statusMessage.includes("🔧") && (
                    <div className="animate-spin rounded-full h-3 w-3 border-b-2 border-primary"></div>
                  )}
                  <span>{statusMessage}</span>
                </div>
              )}
              {streamingContent && (
                <div>
                  <ChatMarkdown content={streamingContent} isUser={false} />
                  <span className="animate-pulse">▊</span>
                </div>
              )}
              {!streamingContent && !statusMessage && (
                <div className="flex items-center space-x-2 text-muted-foreground">
                  <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-primary"></div>
                  <span className="text-sm">Thinking...</span>
                </div>
              )}
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input Area or Generating Message (lock banner is rendered by parent tab) */}
      {isReadOnly ? (
        isLocked ? null : (
          <div className="flex-shrink-0 border-t border-border bg-muted">
            <div className="px-4 py-2">
              <div className="text-center">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto mb-2"></div>
                <p className="text-sm font-medium text-foreground">Project Draft Generating</p>
                <p className="text-xs text-muted-foreground mt-1">
                  Please wait while the project draft is being generated. Chat will be available
                  once complete.
                </p>
              </div>
            </div>
          </div>
        )
      ) : (
        <div className="flex-shrink-0 border-t border-border bg-card">
          {error && (
            <div className="px-4 py-2 bg-destructive/10 border-b border-destructive/30">
              <p className="text-sm text-destructive">{error}</p>
            </div>
          )}

          {/* File Upload Area */}
          {showFileUpload && (
            <div className="px-4 py-4 bg-muted border-b border-border">
              <FileUpload
                conversationId={conversationId}
                onFilesUploaded={handleFilesUploaded}
                disabled={isStreaming}
                maxFiles={5}
                currentModel={currentModel}
                currentProvider={currentProvider}
                modelCapabilities={modelCapabilities}
              />
            </div>
          )}

          {/* Pending Files Display */}
          {pendingFiles.length > 0 && (
            <div className="px-4 py-2 bg-primary/10 border-b border-primary/30">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-medium text-primary">
                  {pendingFiles.length} file{pendingFiles.length !== 1 ? "s" : ""} ready to send
                </span>
                <button
                  onClick={() => setPendingFiles([])}
                  className="text-xs text-primary hover:text-primary/80"
                >
                  Clear all
                </button>
              </div>
              <div className="flex flex-wrap gap-2">
                {pendingFiles.map(file => (
                  <div
                    key={file.s3_key}
                    className="flex items-center space-x-2 bg-card px-2 py-1 rounded border border-border"
                  >
                    <span className="text-sm text-foreground">{file.filename}</span>
                    <button
                      onClick={() => removePendingFile(file.s3_key)}
                      className="text-muted-foreground hover:text-foreground"
                    >
                      ✕
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="px-4 py-4">
            <div className="flex space-x-2 items-end">
              <textarea
                ref={inputRef}
                value={inputMessage}
                onChange={e => setInputMessage(e.target.value)}
                onKeyDown={handleKeyDown}
                disabled={isLoadingHistory || isStreaming || !currentModel}
                rows={1}
                className="flex-1 px-3 py-2 border border-border rounded-lg focus:ring-2 focus:ring-primary focus:border-transparent disabled:opacity-50 disabled:cursor-not-allowed resize-none overflow-hidden bg-card text-foreground"
                style={{
                  minHeight: "40px",
                  maxHeight: "120px",
                  height: "auto",
                }}
                onInput={e => {
                  const target = e.target as HTMLTextAreaElement;
                  target.style.height = "auto";
                  target.style.height = Math.min(target.scrollHeight, 120) + "px";
                }}
                placeholder={
                  isStreaming
                    ? "AI is responding..."
                    : isLoadingHistory
                      ? "Loading..."
                      : !currentModel
                        ? "Loading model settings..."
                        : "Type your message..."
                }
              />

              {/* File Upload Toggle Button */}
              <button
                onClick={() => setShowFileUpload(!showFileUpload)}
                disabled={isLoadingHistory || isStreaming || !currentModel}
                className={`px-3 py-2 h-10 rounded-lg border border-border hover:bg-muted disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center transition-colors ${
                  showFileUpload ? "bg-primary/10 border-primary/30" : "bg-card"
                }`}
                title="Attach files"
              >
                <svg
                  className="w-4 h-4 text-muted-foreground"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13"
                  />
                </svg>
              </button>

              <button
                onClick={sendMessage}
                disabled={
                  isLoadingHistory ||
                  isStreaming ||
                  !currentModel ||
                  (!inputMessage.trim() && pendingFiles.length === 0)
                }
                className="px-4 py-2 h-10 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center"
              >
                {isStreaming ? (
                  <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                ) : (
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"
                    />
                  </svg>
                )}
              </button>
            </div>
            {(isLoadingHistory || !currentModel) && (
              <p className="text-xs text-muted-foreground mt-2">
                {isLoadingHistory ? "Loading chat history..." : "Loading model settings..."}
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
