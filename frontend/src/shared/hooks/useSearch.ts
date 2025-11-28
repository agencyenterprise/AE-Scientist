/**
 * Custom hook for search functionality.
 *
 * Provides search execution, state management, caching, and error handling.
 * All parameters are required following the project's strict typing patterns.
 */

import { useCallback, useMemo, useRef, useState } from "react";

import { config } from "@/shared/lib/config";
import type {
  ErrorResponse,
  SearchContentType,
  SearchParams,
  SearchResponse,
  SearchState,
} from "@/types";

// Constants
// No debouncing used currently
const DEFAULT_PAGE_SIZE = 20;
const CACHE_TTL = 5 * 60 * 1000; // 5 minutes

interface UseSearchReturn {
  // State
  searchState: SearchState;

  // Actions
  search: (query: string) => Promise<void>;
  executeSearch: (params: SearchParams) => Promise<void>;
  loadNextPage: () => Promise<void>;
  clearSearch: () => void;
  setQuery: (query: string) => void;
  setContentTypes: (types: SearchContentType[]) => void;
  setQueryWithDebounce: (
    query: string,
    status: "all" | "in_progress" | "completed",
    sort_by: "updated" | "imported" | "title" | "relevance" | "score",
    sort_dir: "asc" | "desc"
  ) => void;

  // Utilities
  isValidQuery: (query: string) => boolean;
  formatExecutionTime: (timeMs: number) => string;
}

interface CacheEntry<T> {
  data: T;
  timestamp: number;
}

// Helper function to check if response is an error
function isErrorResponse(response: unknown): response is ErrorResponse {
  return (
    typeof response === "object" &&
    response !== null &&
    "error" in response &&
    typeof (response as ErrorResponse).error === "string"
  );
}

export function useSearch(): UseSearchReturn {
  // State management
  const [searchState, setSearchState] = useState<SearchState>({
    query: "",
    results: [],
    stats: null,
    isLoading: false,
    error: null,
    hasMore: false,
    selectedContentTypes: ["conversation", "chat_message", "project_draft"],
    currentPage: 0,
    totalResults: 0,
  });

  // Cache for search results
  const cache = useRef<Map<string, CacheEntry<SearchResponse>>>(new Map());
  const debounceTimer = useRef<NodeJS.Timeout | number | undefined>(undefined);
  const lastParamsRef = useRef<SearchParams | null>(null);
  const DEBOUNCE_DELAY = 500;

  // Helper to create cache key
  const createCacheKey = useCallback((params: SearchParams): string => {
    return `${params.query}-${params.content_types.sort().join(",")}-${params.limit}-${params.offset}-${params.status}-${params.sort_by}-${params.sort_dir}`;
  }, []);

  // Helper to get cached data
  const getCachedData = useCallback((key: string): SearchResponse | null => {
    const entry = cache.current.get(key);
    if (entry && Date.now() - entry.timestamp < CACHE_TTL) {
      return entry.data;
    }
    if (entry) {
      cache.current.delete(key); // Remove expired entry
    }
    return null;
  }, []);

  // Helper to set cached data
  const setCachedData = useCallback((key: string, data: SearchResponse): void => {
    cache.current.set(key, { data, timestamp: Date.now() });
  }, []);

  // Validate search query
  const isValidQuery = useCallback((query: string): boolean => {
    const trimmed = query.trim();
    return trimmed.length >= 2 && trimmed.length <= 500;
  }, []);

  // Format execution time for display
  const formatExecutionTime = useCallback((timeMs: number): string => {
    if (timeMs < 1000) {
      return `${Math.round(timeMs)}ms`;
    }
    return `${(timeMs / 1000).toFixed(1)}s`;
  }, []);

  // Execute search with caching and error handling
  const executeSearch = useCallback(
    async (params: SearchParams): Promise<void> => {
      const { query, content_types, limit, offset, status, sort_by, sort_dir } = params;

      // Validation
      if (!isValidQuery(query)) {
        setSearchState(prev => ({
          ...prev,
          error: "Search query must be between 2 and 500 characters",
          results: [],
          stats: null,
        }));
        return;
      }

      // Check cache first
      const cacheKey = createCacheKey(params);
      const cachedResult = getCachedData(cacheKey);

      if (cachedResult) {
        setSearchState(prev => ({
          ...prev,
          query,
          results: offset === 0 ? cachedResult.results : [...prev.results, ...cachedResult.results],
          stats: cachedResult.stats,
          isLoading: false,
          error: null,
          hasMore: cachedResult.has_more,
          selectedContentTypes: content_types as SearchContentType[],
          currentPage: Math.floor(offset / limit),
          totalResults: cachedResult.total_count,
        }));
        return;
      }

      // Set loading state
      setSearchState(prev => ({
        ...prev,
        query,
        isLoading: true,
        error: null,
        selectedContentTypes: content_types as SearchContentType[],
      }));

      try {
        const searchParams = new URLSearchParams({
          q: query,
          limit: limit.toString(),
          offset: offset.toString(),
          status,
          sort_by,
          sort_dir,
        });

        const response = await fetch(`${config.apiUrl}/search?${searchParams}`, {
          method: "GET",
          credentials: "include",
        });

        const result: SearchResponse | ErrorResponse = await response.json();

        if (!response.ok || isErrorResponse(result)) {
          const errorMessage = isErrorResponse(result) ? result.error : `HTTP ${response.status}`;
          throw new Error(errorMessage);
        }

        // Cache the successful result
        setCachedData(cacheKey, result);
        lastParamsRef.current = params;

        setSearchState(prev => ({
          ...prev,
          results: offset === 0 ? result.results : [...prev.results, ...result.results],
          stats: result.stats,
          isLoading: false,
          error: null,
          hasMore: result.has_more,
          currentPage: Math.floor(offset / limit),
          totalResults: result.total_count,
        }));
      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : "Search failed";
        setSearchState(prev => ({
          ...prev,
          isLoading: false,
          error: errorMessage,
          results: offset === 0 ? [] : prev.results, // Keep existing results for pagination errors
        }));
      }
    },
    [isValidQuery, createCacheKey, getCachedData, setCachedData]
  );

  // Load next page of results
  const loadNextPage = useCallback(async (): Promise<void> => {
    if (searchState.isLoading || !searchState.hasMore || !searchState.query) {
      return;
    }

    const nextOffset = (searchState.currentPage + 1) * DEFAULT_PAGE_SIZE;

    const base = lastParamsRef.current;
    await executeSearch({
      query: searchState.query,
      content_types: base ? base.content_types : searchState.selectedContentTypes,
      limit: base ? base.limit : DEFAULT_PAGE_SIZE,
      offset: nextOffset,
      status: base ? base.status : "all",
      sort_by: base ? base.sort_by : "relevance",
      sort_dir: base ? base.sort_dir : "desc",
    });
  }, [searchState, executeSearch]);

  // Simple search function (searches all content types by default)
  const search = useCallback(
    async (query: string): Promise<void> => {
      // If a debounce is pending, cancel it for immediate search
      if (debounceTimer.current !== undefined) {
        clearTimeout(debounceTimer.current);
      }
      await executeSearch({
        query,
        content_types: ["conversation", "chat_message", "project_draft"],
        limit: DEFAULT_PAGE_SIZE,
        offset: 0,
        status: "all",
        sort_by: "relevance",
        sort_dir: "desc",
      });
    },
    [executeSearch]
  );

  // Clear search state
  const clearSearch = useCallback((): void => {
    // Cancel any pending debounced search
    if (debounceTimer.current !== undefined) {
      clearTimeout(debounceTimer.current);
    }
    setSearchState(prev => ({
      ...prev,
      query: "",
      results: [],
      stats: null,
      error: null,
      hasMore: false,
      currentPage: 0,
      totalResults: 0,
    }));
  }, []);

  // Set search query with debouncing
  const setQuery = useCallback((query: string): void => {
    setSearchState(prev => ({ ...prev, query }));

    // Clear existing debounce timer
    if (debounceTimer.current !== undefined) {
      clearTimeout(debounceTimer.current);
    }

    // Clear results if query becomes empty
    if (!query.trim()) {
      setSearchState(prev => ({
        ...prev,
        results: [],
        stats: null,
        error: null,
        hasMore: false,
      }));
    }
  }, []);

  // Set content types
  const setContentTypes = useCallback(
    (types: SearchContentType[]): void => {
      setSearchState(prev => ({ ...prev, selectedContentTypes: types }));

      // Re-execute search if we have a valid query
      if (isValidQuery(searchState.query)) {
        const base = lastParamsRef.current;
        executeSearch({
          query: searchState.query,
          content_types: types,
          limit: base ? base.limit : DEFAULT_PAGE_SIZE,
          offset: 0,
          status: base ? base.status : "all",
          sort_by: base ? base.sort_by : "relevance",
          sort_dir: base ? base.sort_dir : "desc",
        });
      }
    },
    [searchState.query, executeSearch, isValidQuery]
  );

  // Debounced query setter that also runs search with provided filters/sorting
  const setQueryWithDebounce = useCallback(
    (
      query: string,
      status: "all" | "in_progress" | "completed",
      sort_by: "updated" | "imported" | "title" | "relevance" | "score",
      sort_dir: "asc" | "desc"
    ): void => {
      setSearchState(prev => ({ ...prev, query }));

      // Clear existing debounce timer
      if (debounceTimer.current !== undefined) {
        clearTimeout(debounceTimer.current as number);
      }

      // Clear results if query becomes empty
      if (!query.trim()) {
        setSearchState(prev => ({
          ...prev,
          results: [],
          stats: null,
          error: null,
          hasMore: false,
        }));
        return;
      }

      if (!isValidQuery(query)) {
        return;
      }

      debounceTimer.current = setTimeout(() => {
        executeSearch({
          query,
          content_types: searchState.selectedContentTypes,
          limit: DEFAULT_PAGE_SIZE,
          offset: 0,
          status,
          sort_by,
          sort_dir,
        });
      }, DEBOUNCE_DELAY);
    },
    [executeSearch, isValidQuery, searchState.selectedContentTypes]
  );

  // Memoized return object
  const returnValue = useMemo(
    (): UseSearchReturn => ({
      searchState,
      search,
      executeSearch,
      loadNextPage,
      clearSearch,
      setQuery,
      setContentTypes,
      setQueryWithDebounce,
      isValidQuery,
      formatExecutionTime,
    }),
    [
      searchState,
      search,
      executeSearch,
      loadNextPage,
      clearSearch,
      setQuery,
      setContentTypes,
      setQueryWithDebounce,
      isValidQuery,
      formatExecutionTime,
    ]
  );

  return returnValue;
}
