/**
 * Anti-corruption layer for API responses
 *
 * Converts backend API responses (snake_case, optional fields)
 * to frontend-friendly types (camelCase, required fields with defaults)
 */

import type {
  ConversationResponse,
  ConversationListResponse,
  ConversationListItem,
  ErrorResponse,
  ConversationDetail,
  FileAttachment,
} from "@/types";
import type { components } from "@/types/api.gen";

// ============================================================================
// Frontend-friendly types
// ============================================================================

export interface ConversationMessage {
  role: "user" | "assistant";
  content: string;
  timestamp?: string;
  files?: FileAttachment[];
}

export interface Conversation {
  id: number;
  url: string;
  title: string;
  importDate: string;
  createdAt: string;
  updatedAt: string;
  userId: number;
  userName: string;
  userEmail: string;
  ideaTitle?: string | null;
  ideaMarkdown?: string | null; // Full idea content in markdown format
  lastUserMessageContent?: string | null;
  lastAssistantMessageContent?: string | null;
  conversationStatus?: "draft" | "with_research";
}

// ConversationDetail is imported from main types

// ============================================================================
// Conversion functions (anti-corruption layer)
// ============================================================================

export function convertApiConversation(apiConversation: ConversationListItem): Conversation {
  return {
    id: apiConversation.id,
    url: apiConversation.url,
    title: apiConversation.title,
    importDate: apiConversation.import_date,
    createdAt: apiConversation.created_at,
    updatedAt: apiConversation.updated_at,
    userId: apiConversation.user_id,
    userName: apiConversation.user_name,
    userEmail: apiConversation.user_email,
    ideaTitle: apiConversation.idea_title ?? null,
    ideaMarkdown: apiConversation.idea_content ?? null,
    lastUserMessageContent: apiConversation.last_user_message_content ?? null,
    lastAssistantMessageContent: apiConversation.last_assistant_message_content ?? null,
    conversationStatus:
      "status" in apiConversation && apiConversation.status
        ? (apiConversation.status as "draft" | "with_research")
        : "draft",
  };
}

export function convertApiConversationDetail(
  apiConversation: ConversationResponse
): ConversationDetail {
  return {
    ...apiConversation,
  };
}

export function convertApiConversationList(apiResponse: ConversationListResponse): Conversation[] {
  return apiResponse.conversations.map(convertApiConversation);
}

// ============================================================================
// HTTP status helpers
// ============================================================================

export function isErrorResponse(response: unknown): response is ErrorResponse {
  return (
    typeof response === "object" &&
    response !== null &&
    "error" in response &&
    typeof (response as ErrorResponse).error === "string"
  );
}

// ============================================================================
// Request types
// ============================================================================

export type UpdateSummaryRequest = components["schemas"]["ImportedConversationSummaryUpdate"];

// Helpers for new summary API
export function extractSummary(resp: { summary?: string } | ErrorResponse): string | null {
  if (isErrorResponse(resp)) return null;
  return resp.summary ?? null;
}

// ============================================================================
// Research Run types and converters
// ============================================================================

import type {
  ResearchRun,
  ResearchRunListItemApi,
  ResearchRunListResponseApi,
  ResearchRunListResponse,
} from "@/types/research";

export type { ResearchRun };

export function convertApiResearchRun(apiRun: ResearchRunListItemApi): ResearchRun {
  return {
    runId: apiRun.run_id,
    status: apiRun.status,
    initializationStatus: apiRun.initialization_status,
    ideaTitle: apiRun.idea_title,
    ideaMarkdown: apiRun.idea_hypothesis ?? null, // Backend uses 'idea_hypothesis' but it's actually full markdown
    currentStage: apiRun.current_stage ?? null,
    progress: apiRun.progress ?? null,
    gpuType: apiRun.gpu_type,
    bestMetric: apiRun.best_metric ?? null,
    createdByName: apiRun.created_by_name,
    createdAt: apiRun.created_at,
    updatedAt: apiRun.updated_at,
    artifactsCount: apiRun.artifacts_count,
    errorMessage: apiRun.error_message ?? null,
    conversationId: apiRun.conversation_id,
    parentRunId: apiRun.parent_run_id ?? null,
    evaluationOverall: apiRun.evaluation_overall ?? null,
    evaluationDecision: apiRun.evaluation_decision ?? null,
  };
}

export function convertApiResearchRunList(
  apiResponse: ResearchRunListResponseApi
): ResearchRunListResponse {
  return {
    items: (apiResponse.items ?? []).map(convertApiResearchRun),
    total: apiResponse.total,
  };
}

// ============================================================================
// User types and API functions
// ============================================================================

import { api } from "./api-client-typed";

export type UserListItem = components["schemas"]["UserListItem"];

export async function fetchUsers(): Promise<UserListItem[]> {
  const { data, error } = await api.GET("/api/users/");
  if (error) throw new Error("Failed to fetch users");
  return data?.items ?? [];
}
