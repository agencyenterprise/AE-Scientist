export enum ImportState {
  Importing = "importing",
  ExtractingChatKeywords = "extracting_chat_keywords",
  RetrievingMemories = "retrieving_memories",
  Summarizing = "summarizing",
  Generating = "generating",
}

// Conflict item from API
export interface ConflictItem {
  id: number;
  title: string;
  updated_at: string;
  url: string;
}

export type SSEContent = { type: "content"; data: string };
export type SSEState = { type: "state"; data: ImportState };
export type SSEProgress = {
  type: "progress";
  data: { phase: string; current: number; total: number };
};
export type SSEConflict = {
  type: "conflict";
  data: {
    conversations: Array<{
      id: number;
      title: string;
      updated_at: string;
      url: string;
    }>;
  };
};
export type SSEModelLimit = {
  type: "model_limit_conflict";
  data: { message: string; suggestion: string };
};
export type SSEError = { type: "error"; data: string; code?: string };
export type SSEDone = { type: "done"; data: { conversation?: { id: number }; error?: string } };

export type SSEEvent =
  | SSEContent
  | SSEState
  | SSEProgress
  | SSEConflict
  | SSEModelLimit
  | SSEError
  | SSEDone;
