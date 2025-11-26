"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";

import { ConversationsGrid } from "@/components/ConversationsGrid";
import { DashboardHeader } from "@/components/DashboardHeader";
import { SearchResults } from "@/components/Search";
import { DashboardFilterSortBar } from "@/components/DashboardFilterSortBar";
import { useSearch } from "@/hooks/useSearch";
import { useDashboard } from "./DashboardContext";
import type { SortDir, SortKey } from "./DashboardContext";
import type { SearchSortBy } from "@/types";
import { getSearchSortByFromSortKey } from "@/lib/searchUtils";

export default function Home() {
  const {
    conversations,
    selectConversation,
    linearFilter,
    sortKey,
    sortDir,
    setSortKey,
    setSortDir,
  } = useDashboard();
  const searchParams = useSearchParams();
  const {
    searchState,
    search,
    executeSearch,
    loadNextPage,
    clearSearch,
    setQuery,
    setQueryWithDebounce,
    isValidQuery,
  } = useSearch();

  // Initialize from URL (?q=)
  const hasInitializedFromUrl = useRef(false);
  const urlQuery = searchParams.get("q") || "";

  useEffect(() => {
    if (urlQuery && isValidQuery(urlQuery) && !hasInitializedFromUrl.current) {
      hasInitializedFromUrl.current = true;
      setQuery(urlQuery);
      search(urlQuery);
    }
  }, [urlQuery, search, setQuery, isValidQuery]);

  // Helpers to DRY sort mapping and first-search behavior
  const getSortBy = useCallback((key: SortKey): SearchSortBy => {
    return getSearchSortByFromSortKey(key);
  }, []);

  const computeSortParams = useCallback(
    (query: string): { sort_by: SearchSortBy; sort_dir: SortDir } => {
      const willStartSearch = !searchState.query && Boolean(query.trim());
      const effectiveSortKey = willStartSearch ? "score" : sortKey;
      if (willStartSearch && sortKey !== "score") {
        setSortKey("score");
        setSortDir("desc");
      }
      const sort_by = getSortBy(effectiveSortKey as SortKey);
      const sort_dir: SortDir = sortDir;
      return { sort_by, sort_dir };
    },
    [searchState.query, sortKey, sortDir, setSortKey, setSortDir, getSortBy]
  );

  // Handlers for SearchBox
  const handleSearch = useCallback(
    (query: string) => {
      const newUrl = new URL(window.location.href);
      newUrl.searchParams.set("q", query);
      window.history.pushState({}, "", newUrl.toString());

      const status = linearFilter;
      const { sort_by, sort_dir } = computeSortParams(query);
      executeSearch({
        query,
        content_types: ["conversation", "chat_message", "project_draft"],
        limit: 20,
        offset: 0,
        status,
        sort_by,
        sort_dir,
      });
    },
    [executeSearch, linearFilter, computeSortParams]
  );

  const handleQueryChange = useCallback(
    (query: string) => {
      const status = linearFilter;
      const { sort_by, sort_dir } = computeSortParams(query);
      setQueryWithDebounce(query, status, sort_by, sort_dir);
    },
    [setQueryWithDebounce, linearFilter, computeSortParams]
  );

  const handleClear = useCallback(() => {
    const newUrl = new URL(window.location.href);
    newUrl.searchParams.delete("q");
    window.history.pushState({}, "", newUrl.toString());
    clearSearch();
  }, [clearSearch]);

  // Re-apply filters/sorting to search when they change and a query is active
  useEffect(() => {
    if (!searchState.query || !isValidQuery(searchState.query)) return;
    const status = linearFilter;
    const sort_by = getSortBy(sortKey);
    const sort_dir = sortDir;
    executeSearch({
      query: searchState.query,
      content_types: searchState.selectedContentTypes,
      limit: 20,
      offset: 0,
      status,
      sort_by,
      sort_dir,
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [linearFilter, sortKey, sortDir]);

  // Responsive placeholder text
  const [isSmallScreen, setIsSmallScreen] = useState(false);
  useEffect(() => {
    if (typeof window === "undefined") return;
    const mql = window.matchMedia("(max-width: 640px)");
    const update = (e?: MediaQueryListEvent) => setIsSmallScreen(e ? e.matches : mql.matches);
    update();
    mql.addEventListener("change", update);
    return () => mql.removeEventListener("change", update);
  }, []);

  const placeholderText = useMemo(() => {
    return isSmallScreen
      ? "Search conversations & drafts"
      : "Search across conversations, chats, and project drafts...";
  }, [isSmallScreen]);

  const searchBoxProps = useMemo(
    () => ({
      query: searchState.query,
      isLoading: searchState.isLoading,
      placeholder: placeholderText,
      onQueryChange: handleQueryChange,
      onSearch: handleSearch,
      onClear: handleClear,
      disabled: false,
    }),
    [
      searchState.query,
      searchState.isLoading,
      handleQueryChange,
      handleSearch,
      handleClear,
      placeholderText,
    ]
  );

  const searchResultsProps = useMemo(
    () => ({
      results: searchState.results,
      stats: searchState.stats,
      isLoading: searchState.isLoading,
      hasMore: searchState.hasMore,
      onLoadMore: loadNextPage,
      query: searchState.query,
      error: searchState.error,
    }),
    [
      searchState.results,
      searchState.stats,
      searchState.isLoading,
      searchState.hasMore,
      searchState.query,
      searchState.error,
      loadNextPage,
    ]
  );

  const shouldShowSearch = useMemo(() => {
    return Boolean(
      searchState.query ||
        searchState.isLoading ||
        searchState.results.length > 0 ||
        searchState.error
    );
  }, [searchState.query, searchState.isLoading, searchState.results.length, searchState.error]);

  return (
    <div className="h-full flex flex-col">
      <DashboardHeader searchBoxProps={searchBoxProps} />
      <DashboardFilterSortBar hasQuery={Boolean(searchState.query)} />
      <div className="flex-1 min-h-0 overflow-y-auto">
        {shouldShowSearch ? (
          <div className="p-4 sm:p-6 bg-gray-50">
            <SearchResults {...searchResultsProps} />
          </div>
        ) : (
          <ConversationsGrid conversations={conversations} onSelect={selectConversation} />
        )}
      </div>
    </div>
  );
}
