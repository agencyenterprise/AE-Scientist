/**
 * Search-related TypeScript types.
 *
 * These types match the backend Pydantic models exactly.
 * All properties are required unless explicitly marked optional.
 */

// ============================================================================
// Search Result Types
// ============================================================================

export interface SearchResult {
  id: number;
  content_type: string;
  content_snippet: string;
  score: number;
  created_at: string;
  conversation_id: number;
  conversation_title: string;
  created_by_user_name: string;
  created_by_user_email: string;
}

export interface SearchStats {
  query: string;
  total_results: number;
  execution_time_ms: number;
  results_by_type: Record<string, number>;
}

export interface SearchResponse {
  results: SearchResult[];
  stats: SearchStats;
  total_count: number;
  has_more: boolean;
}

// ============================================================================
// Search Request Types (for frontend use)
// ============================================================================

export interface SearchParams {
  query: string;
  content_types: string[];
  limit: number;
  offset: number;
  status: "all" | "in_progress" | "completed";
  sort_by: "updated" | "imported" | "title" | "relevance" | "score";
  sort_dir: "asc" | "desc";
}

export type SearchStatus = "all" | "in_progress" | "completed";
export type SearchSortBy = "updated" | "imported" | "title" | "relevance" | "score";
export type SearchSortDir = "asc" | "desc";

// ============================================================================
// Content Type Constants
// ============================================================================

export const SEARCH_CONTENT_TYPES = ["conversation", "chat_message", "project_draft"] as const;

export type SearchContentType = (typeof SEARCH_CONTENT_TYPES)[number];

// ============================================================================
// Search UI State Types
// ============================================================================

export interface SearchState {
  query: string;
  results: SearchResult[];
  stats: SearchStats | null;
  isLoading: boolean;
  error: string | null;
  hasMore: boolean;
  selectedContentTypes: SearchContentType[];
  currentPage: number;
  totalResults: number;
}

export interface SearchFormState {
  query: string;
  selectedTypes: SearchContentType[];
  showFilters: boolean;
}

// ============================================================================
// Search Event Types
// ============================================================================

export interface SearchExecutedEvent {
  query: string;
  content_types: SearchContentType[];
  results_count: number;
  execution_time_ms: number;
}

export interface SearchErrorEvent {
  query: string;
  error_message: string;
  error_type: "validation" | "network" | "server";
}
