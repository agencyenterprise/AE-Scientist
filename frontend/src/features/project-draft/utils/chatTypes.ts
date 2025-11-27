import { ChatStatus } from "@/types";

// Type-safe status message mapping with compile-time completeness check
export const STATUS_MESSAGES: Record<ChatStatus, string> = {
  [ChatStatus.ANALYZING_REQUEST]: "Analyzing your request...",
  [ChatStatus.EXECUTING_TOOLS]: "Processing...",
  [ChatStatus.GETTING_IDEA]: "Getting current idea...",
  [ChatStatus.UPDATING_IDEA]: "Updating idea...",
  [ChatStatus.GENERATING_RESPONSE]: "Generating response...",
  [ChatStatus.DONE]: "",
};

// Type guard function to check if a string is a valid ChatStatus
export function isChatStatus(value: string): value is ChatStatus {
  return Object.values(ChatStatus).includes(value as ChatStatus);
}

// Format timestamp for chat messages
export function formatTimestamp(timestamp: string): string {
  return new Date(timestamp).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });
}
