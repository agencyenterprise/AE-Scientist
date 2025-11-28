import { ChatMarkdown } from "./ChatMarkdown";

interface ChatStreamingMessageProps {
  statusMessage: string;
  streamingContent: string;
}

export function ChatStreamingMessage({
  statusMessage,
  streamingContent,
}: ChatStreamingMessageProps) {
  return (
    <div className="flex items-start space-x-3">
      <div className="flex-shrink-0 w-8 h-8 bg-primary rounded-full flex items-center justify-center text-primary-foreground text-sm font-medium">
        AI
      </div>
      <div className="flex-1 bg-muted rounded-lg px-4 py-2 max-w-3xl min-w-0 break-words overflow-hidden">
        {statusMessage && (
          <div className="text-sm text-muted-foreground mb-2 font-medium flex items-center space-x-2">
            {statusMessage.includes("Processing") && (
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
  );
}
