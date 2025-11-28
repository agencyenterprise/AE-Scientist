/**
 * Search utility functions.
 *
 * Provides text highlighting, snippet generation, and search-related
 * formatting utilities for the search interface.
 */

// Constants
export const DEFAULT_SNIPPET_LENGTH = 200;
export const MIN_HIGHLIGHT_WORD_LENGTH = 1; // Allow single character highlighting like "fa"
export const ELLIPSIS = "...";

/**
 * Highlight search terms in text content with HTML mark tags.
 *
 * @param text - The text content to highlight
 * @param query - The search query containing terms to highlight
 * @param className - CSS class for the highlight marks (default: "bg-yellow-200 px-0.5 rounded")
 * @returns HTML string with highlighted terms
 */
export function highlightSearchTerms(
  text: string,
  query: string,
  className: string = "bg-yellow-200 px-0.5 rounded"
): string {
  if (!text || !query.trim()) {
    return text;
  }

  // Extract meaningful words from query (ignore short words)
  const queryWords = query
    .trim()
    .toLowerCase()
    .split(/\s+/)
    .filter(word => word.length >= MIN_HIGHLIGHT_WORD_LENGTH)
    .map(word => word.replace(/[^a-z0-9]/gi, "")); // Remove special characters

  if (queryWords.length === 0) {
    return text;
  }

  let highlightedText = text;

  // Highlight each query word
  queryWords.forEach(word => {
    if (word.length === 0) return;

    // Create regex that matches partial words - more aggressive for short queries
    const regex = new RegExp(`(\\w*${word}\\w*)`, "gi");

    highlightedText = highlightedText.replace(regex, `<mark class="${className}">$1</mark>`);
  });

  return highlightedText;
}

/**
 * Create a content snippet centered around the first occurrence of search terms.
 *
 * @param content - Full text content
 * @param query - Search query
 * @param maxLength - Maximum snippet length
 * @returns Content snippet with ellipsis if truncated
 */
export function createSearchSnippet(
  content: string,
  query: string,
  maxLength: number = DEFAULT_SNIPPET_LENGTH
): string {
  if (!content) {
    return "";
  }

  if (content.length <= maxLength) {
    return content;
  }

  if (!query.trim()) {
    return content.slice(0, maxLength) + ELLIPSIS;
  }

  // Find the first occurrence of any query word
  const queryWords = query
    .trim()
    .toLowerCase()
    .split(/\s+/)
    .filter(word => word.length >= MIN_HIGHLIGHT_WORD_LENGTH);

  if (queryWords.length === 0) {
    return content.slice(0, maxLength) + ELLIPSIS;
  }

  const contentLower = content.toLowerCase();
  let firstMatchPos = content.length;

  // Find the earliest occurrence of any query word
  for (const word of queryWords) {
    const pos = contentLower.indexOf(word);
    if (pos !== -1) {
      firstMatchPos = Math.min(firstMatchPos, pos);
    }
  }

  if (firstMatchPos === content.length) {
    // No matches found, return beginning
    return content.slice(0, maxLength) + ELLIPSIS;
  }

  // Create snippet centered around first match
  const padding = Math.floor((maxLength - query.length) / 2);
  const startPos = Math.max(0, firstMatchPos - padding);
  const endPos = Math.min(content.length, startPos + maxLength);

  const snippet = content.slice(startPos, endPos);

  // Add ellipsis if truncated
  let result = "";
  if (startPos > 0) {
    result += ELLIPSIS;
  }
  result += snippet;
  if (endPos < content.length) {
    result += ELLIPSIS;
  }

  return result;
}

/**
 * Combine snippet generation and highlighting in one operation.
 *
 * @param content - Full text content
 * @param query - Search query
 * @param maxLength - Maximum snippet length
 * @param highlightClassName - CSS class for highlights
 * @returns HTML string with highlighted snippet
 */
export function createHighlightedSnippet(
  content: string,
  query: string,
  maxLength: number = DEFAULT_SNIPPET_LENGTH,
  highlightClassName: string = "bg-yellow-200 px-0.5 rounded"
): string {
  const snippet = createSearchSnippet(content, query, maxLength);
  return highlightSearchTerms(snippet, query, highlightClassName);
}

/**
 * Escape HTML special characters to prevent XSS.
 *
 * @param text - Text to escape
 * @returns HTML-escaped text
 */
export function escapeHtml(text: string): string {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

/**
 * Create safe highlighted content by escaping HTML first, then highlighting.
 *
 * @param content - Raw text content
 * @param query - Search query
 * @param maxLength - Maximum snippet length
 * @param highlightClassName - CSS class for highlights
 * @returns Safe HTML string with highlighted snippet
 */
export function createSafeHighlightedSnippet(
  content: string,
  query: string,
  maxLength: number = DEFAULT_SNIPPET_LENGTH,
  highlightClassName: string = "bg-yellow-200 px-0.5 rounded"
): string {
  // First escape the content for safety
  const escapedContent = escapeHtml(content);

  // Then create highlighted snippet
  return createHighlightedSnippet(escapedContent, query, maxLength, highlightClassName);
}

/**
 * Format search execution time for display.
 *
 * @param timeMs - Execution time in milliseconds
 * @returns Formatted time string
 */
export function formatSearchTime(timeMs: number): string {
  if (timeMs < 1000) {
    return `${Math.round(timeMs)}ms`;
  } else if (timeMs < 60000) {
    return `${(timeMs / 1000).toFixed(1)}s`;
  } else {
    return `${Math.floor(timeMs / 60000)}m ${Math.round((timeMs % 60000) / 1000)}s`;
  }
}

/**
 * Validate search query format and length.
 *
 * @param query - Search query string
 * @returns Object with validation result and error message
 */
export function validateSearchQuery(query: string): { isValid: boolean; error?: string } {
  const trimmed = query.trim();

  if (!trimmed) {
    return { isValid: false, error: "Search query cannot be empty" };
  }

  if (trimmed.length < 2) {
    return { isValid: false, error: "Search query must be at least 2 characters" };
  }

  if (trimmed.length > 500) {
    return { isValid: false, error: "Search query is too long (max 500 characters)" };
  }

  // Check for potentially dangerous patterns
  const dangerousPatterns = [";", "--", "/*", "*/"];
  const queryLower = trimmed.toLowerCase();

  for (const pattern of dangerousPatterns) {
    if (queryLower.includes(pattern)) {
      return { isValid: false, error: `Search query contains invalid characters: ${pattern}` };
    }
  }

  return { isValid: true };
}

/**
 * Get user-friendly content type label.
 *
 * @param contentType - Raw content type from backend
 * @returns Human-readable content type label
 */
export function getContentTypeLabel(contentType: string): string {
  switch (contentType) {
    case "conversation":
      return "Conversation";
    case "chat_message":
      return "Chat Message";
    case "project_draft":
      return "Project Draft";
    default:
      return contentType.replace(/_/g, " ").replace(/\b\w/g, l => l.toUpperCase());
  }
}

// =========================================================================
// Sort mapping helpers
// =========================================================================
import type { SearchSortBy } from "@/types";
import type { SortKey } from "@/features/dashboard/contexts/DashboardContext";

/**
 * Map dashboard SortKey to backend SearchSortBy param.
 */
export function getSearchSortByFromSortKey(key: SortKey): SearchSortBy {
  return key === "score"
    ? "score"
    : key === "title"
      ? "title"
      : key === "imported"
        ? "imported"
        : "updated";
}
