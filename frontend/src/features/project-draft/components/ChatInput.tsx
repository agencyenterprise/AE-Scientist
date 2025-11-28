import { useRef, useCallback } from "react";
import { Paperclip, Send, Loader2 } from "lucide-react";

interface ChatInputProps {
  inputMessage: string;
  onInputChange: (value: string) => void;
  onSendMessage: () => void;
  onToggleFileUpload: () => void;
  isLoadingHistory: boolean;
  isStreaming: boolean;
  currentModel: string;
  showFileUpload: boolean;
  pendingFilesCount: number;
  inputRef?: React.RefObject<HTMLTextAreaElement | null>;
}

export function ChatInput({
  inputMessage,
  onInputChange,
  onSendMessage,
  onToggleFileUpload,
  isLoadingHistory,
  isStreaming,
  currentModel,
  showFileUpload,
  pendingFilesCount,
  inputRef: externalInputRef,
}: ChatInputProps) {
  const internalInputRef = useRef<HTMLTextAreaElement>(null);
  const inputRef = externalInputRef || internalInputRef;

  const handleKeyDown = useCallback(
    (event: React.KeyboardEvent<HTMLTextAreaElement>): void => {
      if (
        event.key === "Enter" &&
        !event.shiftKey &&
        !event.metaKey &&
        !event.ctrlKey &&
        !isStreaming
      ) {
        event.preventDefault();
        onSendMessage();
      }
      // Cmd+Return or Ctrl+Return allows line breaks
      // Shift+Enter also allows line breaks (default textarea behavior)
    },
    [isStreaming, onSendMessage]
  );

  const handleInput = useCallback((e: React.FormEvent<HTMLTextAreaElement>) => {
    const target = e.target as HTMLTextAreaElement;
    target.style.height = "auto";
    target.style.height = Math.min(target.scrollHeight, 120) + "px";
  }, []);

  const isDisabled = isLoadingHistory || isStreaming || !currentModel;
  const canSend = !isDisabled && (inputMessage.trim() || pendingFilesCount > 0);

  const placeholder = isStreaming
    ? "AI is responding..."
    : isLoadingHistory
      ? "Loading..."
      : !currentModel
        ? "Loading model settings..."
        : "Type your message...";

  return (
    <div className="px-4 py-4">
      <div className="flex space-x-2 items-end">
        <textarea
          ref={inputRef as React.RefObject<HTMLTextAreaElement>}
          value={inputMessage}
          onChange={e => onInputChange(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={isDisabled}
          rows={1}
          className="flex-1 px-3 py-2 border border-border rounded-lg focus:ring-2 focus:ring-primary focus:border-transparent disabled:opacity-50 disabled:cursor-not-allowed resize-none overflow-hidden bg-card text-foreground"
          style={{
            minHeight: "40px",
            maxHeight: "120px",
            height: "auto",
          }}
          onInput={handleInput}
          placeholder={placeholder}
        />

        {/* File Upload Toggle Button */}
        <button
          onClick={onToggleFileUpload}
          disabled={isDisabled}
          className={`px-3 py-2 h-10 rounded-lg border border-border hover:bg-muted disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center transition-colors ${
            showFileUpload ? "bg-primary/10 border-primary/30" : "bg-card"
          }`}
          title="Attach files"
        >
          <Paperclip className="w-4 h-4 text-muted-foreground" />
        </button>

        <button
          onClick={onSendMessage}
          disabled={!canSend}
          className="p-3 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center"
        >
          {isStreaming ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Send className="w-4 h-4" />
          )}
        </button>
      </div>
      {(isLoadingHistory || !currentModel) && (
        <p className="text-xs text-muted-foreground mt-2">
          {isLoadingHistory ? "Loading chat history..." : "Loading model settings..."}
        </p>
      )}
    </div>
  );
}
