"use client";

import { Search, Lightbulb } from "lucide-react";
import { cn } from "@/shared/lib/utils";
import type { IdeationQueueHeaderProps } from "../types/ideation-queue.types";
import type { ConversationStatusFilter, RunStatusFilter } from "../types/conversation-filter.types";
import {
  CONVERSATION_STATUS_OPTIONS,
  CONVERSATION_STATUS_FILTER_CONFIG,
  RUN_STATUS_OPTIONS,
  RUN_STATUS_FILTER_CONFIG,
} from "../utils/conversation-filter-utils";

interface ExtendedIdeationQueueHeaderProps extends IdeationQueueHeaderProps {
  conversationStatusFilter?: ConversationStatusFilter;
  onConversationStatusChange?: (filter: ConversationStatusFilter) => void;
  runStatusFilter?: RunStatusFilter;
  onRunStatusChange?: (filter: RunStatusFilter) => void;
}

/**
 * Header component for the Ideation Queue page
 * Includes title, count, filter toggles, and search input
 */
export function IdeationQueueHeader({
  searchTerm,
  onSearchChange,
  totalCount,
  filteredCount,
  conversationStatusFilter = "all",
  onConversationStatusChange,
  runStatusFilter = "all",
  onRunStatusChange,
}: ExtendedIdeationQueueHeaderProps) {
  const showingFiltered = filteredCount !== totalCount;

  return (
    <div className="space-y-4">
      {/* Title and count row */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <Lightbulb className="h-6 w-6 text-amber-400" />
          <div>
            <h1 className="text-xl font-semibold text-white">Ideation Queue</h1>
            <p className="text-sm text-slate-400">
              {showingFiltered
                ? `Showing ${filteredCount} of ${totalCount} idea${totalCount !== 1 ? "s" : ""}`
                : `${totalCount} idea${totalCount !== 1 ? "s" : ""}`}
            </p>
          </div>
        </div>
      </div>

      <div className="flex flex-row gap-6 items-center">
        {/* Search row */}
        <div className="relative w-full max-w-2xl">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
          <input
            type="search"
            role="searchbox"
            aria-label="Search ideas"
            placeholder="Search ideas..."
            value={searchTerm}
            onChange={e => onSearchChange(e.target.value)}
            className="w-full rounded-lg border border-slate-800 bg-slate-900/50 py-2 pl-10 pr-4 text-sm text-slate-100 placeholder-slate-500 transition-colors focus:border-slate-700 focus:outline-none focus:ring-1 focus:ring-slate-700"
          />
        </div>

        {/* Filter toggles row - Conversation Status */}
        {onConversationStatusChange && (
          <div className="flex flex-col gap-2">
            <label className="text-xs font-medium text-slate-400">Conversation Status</label>
            <div
              className="flex items-center gap-1"
              role="group"
              aria-label="Filter by conversation status"
            >
              {CONVERSATION_STATUS_OPTIONS.map(option => (
                <button
                  key={option}
                  type="button"
                  onClick={() => onConversationStatusChange(option)}
                  aria-pressed={conversationStatusFilter === option}
                  className={cn(
                    "rounded-md px-3 py-1 text-xs font-medium transition-colors",
                    conversationStatusFilter === option
                      ? CONVERSATION_STATUS_FILTER_CONFIG[option].activeClass
                      : "text-slate-500 hover:bg-slate-800 hover:text-slate-300"
                  )}
                >
                  {CONVERSATION_STATUS_FILTER_CONFIG[option].label}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Filter toggles row - Run Status */}
        {onRunStatusChange && (
          <div className="flex flex-col gap-2">
            <label className="text-xs font-medium text-slate-400">Run Status</label>
            <div className="flex items-center gap-1" role="group" aria-label="Filter by run status">
              {RUN_STATUS_OPTIONS.map(option => (
                <button
                  key={option}
                  type="button"
                  onClick={() => onRunStatusChange(option)}
                  aria-pressed={runStatusFilter === option}
                  className={cn(
                    "rounded-md px-3 py-1 text-xs font-medium transition-colors",
                    runStatusFilter === option
                      ? RUN_STATUS_FILTER_CONFIG[option].activeClass
                      : "text-slate-500 hover:bg-slate-800 hover:text-slate-300"
                  )}
                >
                  {RUN_STATUS_FILTER_CONFIG[option].label}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
