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
  ideaAbstract?: string | null;
  lastUserMessageContent?: string | null;
  lastAssistantMessageContent?: string | null;
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
    ideaAbstract: apiConversation.idea_abstract ?? null,
    lastUserMessageContent: apiConversation.last_user_message_content ?? null,
    lastAssistantMessageContent: apiConversation.last_assistant_message_content ?? null,
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

export interface UpdateSummaryRequest {
  summary: string;
}

// Helpers for new summary API
export function extractSummary(resp: { summary?: string } | ErrorResponse): string | null {
  if (isErrorResponse(resp)) return null;
  return resp.summary ?? null;
}

export type SearchScope = "imported_chat" | "draft_chat" | "project_draft";

export interface BaseResult {
  sourceType: SearchScope;
  snippet: string;
  score: number;
}
export interface ImportedChatResult extends BaseResult {
  sourceType: "imported_chat";
  conversationId: number;
  messageIndex: number;
  chunkIndex: number;
}
export interface DraftChatResult extends BaseResult {
  sourceType: "draft_chat";
  projectDraftId: number;
  projectDraftVersionId: number;
  chatMessageId: number;
  sequenceNumber: number;
  chunkIndex: number;
}
export interface ProjectDraftResult extends BaseResult {
  sourceType: "project_draft";
  projectDraftId: number;
  projectDraftVersionId: number;
  chunkIndex: number;
}

export type SearchResult = ImportedChatResult | DraftChatResult | ProjectDraftResult;

export async function searchApi({
  query,
  scopes,
  top_k,
}: {
  query: string;
  scopes: SearchScope[];
  top_k: number;
}): Promise<SearchResult[]> {
  const res = await fetch(`/api/search`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, scopes, top_k }),
  });
  if (!res.ok) {
    return [];
  }
  const data = await res.json();
  return data.results as SearchResult[];
}
