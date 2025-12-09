import type { ComponentType } from "react";
import type { Conversation } from "@/shared/lib/api-adapters";

/**
 * Conversation status type
 * - "draft": Conversation without research
 * - "with_research": Conversation with research runs
 */
export type ConversationStatus = "draft" | "with_research";

/**
 * Status types for ideation queue items
 * Ordered by workflow progression for sorting
 */
export type IdeaStatus =
  | "no_idea" // No ideaTitle/ideaAbstract present
  | "pending_launch" // Has idea but no research run (MVP: default if has idea)
  | "in_research" // Active research run (future: from backend)
  | "completed" // Research completed (future: from backend)
  | "failed"; // Research failed (future: from backend)

/**
 * Filter options including "all" for showing everything
 */
export type StatusFilterOption = "all" | IdeaStatus;

/**
 * Configuration for status badge styling (OCP-compliant)
 */
export interface IdeaStatusConfig {
  label: string;
  className: string;
  icon: ComponentType<{ className?: string }>;
}

/**
 * Configuration for filter button styling (OCP-compliant)
 */
export interface StatusFilterConfig {
  label: string;
  activeClass: string;
}

/**
 * Sort options for ideation queue
 */
export type IdeationSortKey = "newest" | "oldest" | "title_asc" | "title_desc" | "status";

/**
 * Props for IdeationQueueCard component (ISP-compliant: focused interface)
 * MODIFIED: Added optional selection props for inline view support
 * MODIFIED: Added conversationStatus prop for status badge display
 */
export interface IdeationQueueCardProps {
  id: number;
  title: string;
  abstract: string | null;
  status: IdeaStatus;
  conversationStatus?: ConversationStatus;
  createdAt: string;
  updatedAt: string;
  /** Whether this card is currently selected for inline view */
  isSelected?: boolean;
  /** Callback when card is selected (if not provided, defaults to navigation) */
  onSelect?: (id: number) => void;
}

/**
 * Props for IdeationQueueFilters component
 */
export interface IdeationQueueFiltersProps {
  activeFilter: StatusFilterOption;
  onFilterChange: (filter: StatusFilterOption) => void;
}

/**
 * Props for IdeationQueueHeader component
 */
export interface IdeationQueueHeaderProps {
  searchTerm: string;
  onSearchChange: (term: string) => void;
  totalCount: number;
  filteredCount: number;
}

/**
 * Props for IdeationQueueList component
 * MODIFIED: Added optional selection props for inline view support
 */
export interface IdeationQueueListProps {
  conversations: Conversation[];
  emptyMessage?: string;
  /** ID of currently selected conversation */
  selectedId?: number | null;
  /** Callback when a conversation is selected */
  onSelect?: (id: number) => void;
}

/**
 * Props for IdeationQueueEmpty component
 */
export interface IdeationQueueEmptyProps {
  hasFilters?: boolean;
}

/**
 * Extended return type for useConversationsFilter hook
 */
export interface UseConversationsFilterReturn {
  searchTerm: string;
  setSearchTerm: (term: string) => void;
  statusFilter: StatusFilterOption;
  setStatusFilter: (filter: StatusFilterOption) => void;
  filteredConversations: Conversation[];
}

// ============================================================================
// Research Run Types for Ideation Queue Display
// ============================================================================

import type { ConversationResponse } from "@/types";

/**
 * Research run summary type derived from API schema.
 * Uses NonNullable to extract the array element type from ConversationResponse.
 */
export type ResearchRunSummary = NonNullable<ConversationResponse["research_runs"]>[number];

/**
 * Research run status for display purposes.
 * Matches backend status values from ResearchRunSummary.
 */
export type RunStatus = "pending" | "running" | "completed" | "failed";

/**
 * Props for IdeationQueueRunItem component (ISP-compliant: minimal interface)
 */
export interface IdeationQueueRunItemProps {
  runId: string;
  status: string;
  gpuType: string | null;
  createdAt: string;
}

/**
 * Props for IdeationQueueRunsList component
 */
export interface IdeationQueueRunsListProps {
  conversationId: number;
}

/**
 * Return type for useConversationResearchRuns hook
 */
export interface UseConversationResearchRunsReturn {
  runs: ResearchRunSummary[];
  isLoading: boolean;
  error: string | null;
  refetch: () => void;
}

// ============================================================================
// Inline Idea View Types
// ============================================================================

import type { Idea } from "@/types";

/**
 * Props for InlineIdeaView component
 * Focused interface per ISP - only needs conversation ID
 */
export interface InlineIdeaViewProps {
  conversationId: number | null;
}

/**
 * Return type for useSelectedIdeaData hook
 */
export interface UseSelectedIdeaDataReturn {
  idea: Idea | null;
  isLoading: boolean;
  error: string | null;
  refetch: () => void;
}
