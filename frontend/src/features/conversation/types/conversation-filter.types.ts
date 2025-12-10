/**
 * Conversation status filter options for API query
 * 'all' = no filter applied (omit param from request)
 */
export type ConversationStatusFilter = "all" | "draft" | "with_research";

/**
 * Run status filter options for API query
 * 'all' = no filter applied (omit param from request)
 */
export type RunStatusFilter = "all" | "pending" | "running" | "completed" | "failed";

/**
 * Filter configuration for toggle buttons (OCP-compliant)
 */
export interface FilterConfig {
  label: string;
  activeClass: string;
}
