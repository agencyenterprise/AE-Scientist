import type { ConversationImportStreamEvent } from "@/types";

export enum ImportState {
  Importing = "importing",
  CreatingManualSeed = "creating_manual_seed",
  Summarizing = "summarizing",
  Generating = "generating",
}

export type SSEEvent = ConversationImportStreamEvent;
export type SSEContent = Extract<SSEEvent, { type: "content" }>;
export type SSESectionUpdate = Extract<SSEEvent, { type: "section_update" }>;
export type SSEState = Extract<SSEEvent, { type: "state" }>;
export type SSEProgress = Extract<SSEEvent, { type: "progress" }>;
export type SSEConflict = Extract<SSEEvent, { type: "conflict" }>;
export type SSEModelLimit = Extract<SSEEvent, { type: "model_limit_conflict" }>;
export type SSEError = Extract<SSEEvent, { type: "error" }>;
export type SSEDone = Extract<SSEEvent, { type: "done" }>;

export type ConflictItem = SSEConflict["data"]["conversations"][number];
