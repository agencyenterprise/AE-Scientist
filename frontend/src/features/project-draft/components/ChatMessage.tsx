import type { ChatMessage as ChatMessageType } from "@/types";

import { ChatMarkdown } from "./ChatMarkdown";
import { formatTimestamp } from "../utils/chatTypes";

interface ChatMessageProps {
  message: ChatMessageType;
}

export function ChatMessage({ message }: ChatMessageProps) {
  const isUser = message.role === "user";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"} overflow-hidden`}>
      <div
        className={`max-w-[80%] min-w-0 rounded-lg px-4 py-2 break-words overflow-hidden ${
          isUser
            ? "bg-primary text-primary-foreground"
            : "bg-muted text-foreground border border-border"
        }`}
      >
        <ChatMarkdown content={message.content} isUser={isUser} attachments={message.attachments} />
        <div
          className={`text-xs mt-1 flex items-center space-x-2 ${
            isUser ? "text-primary-foreground/70" : "text-muted-foreground"
          }`}
        >
          <span>{isUser ? message.sent_by_user_name : "Assistant"}</span>
          <span>•</span>
          <span>{formatTimestamp(message.created_at)}</span>
        </div>
      </div>
    </div>
  );
}
