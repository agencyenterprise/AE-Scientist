"use client";

import { Search, Lightbulb, ChevronDown } from "lucide-react";
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
 * Uses dropdowns on mobile, pill buttons on desktop
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
      <div className="flex items-center gap-3">
        <Lightbulb className="h-6 w-6 text-amber-400 shrink-0" />
        <div>
          <h1 className="text-xl font-semibold text-white">Ideation Queue</h1>
          <p className="text-sm text-slate-400">
            {showingFiltered
              ? `Showing ${filteredCount} of ${totalCount} idea${totalCount !== 1 ? "s" : ""}`
              : `${totalCount} idea${totalCount !== 1 ? "s" : ""}`}
          </p>
        </div>
      </div>

      {/* Search row */}
      <div className="relative w-full">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
        <input
          type="search"
          role="searchbox"
          aria-label="Search ideas"
          placeholder="Search ideas..."
          value={searchTerm}
          onChange={e => onSearchChange(e.target.value)}
          className="w-full rounded-lg border border-slate-800 bg-slate-900/50 py-2.5 pl-10 pr-4 text-sm text-slate-100 placeholder-slate-500 transition-colors focus:border-slate-700 focus:outline-none focus:ring-1 focus:ring-slate-700"
        />
      </div>

      {/* Mobile: Dropdown filters */}
      <div className="flex gap-3 md:hidden">
        {onConversationStatusChange && (
          <div className="flex-1 space-y-1.5">
            <label className="text-xs font-medium text-slate-400">Status</label>
            <div className="relative">
              <select
                value={conversationStatusFilter}
                onChange={e =>
                  onConversationStatusChange(e.target.value as ConversationStatusFilter)
                }
                aria-label="Filter by conversation status"
                className="w-full appearance-none rounded-lg border border-slate-800 bg-slate-900/50 py-2.5 pl-3 pr-10 text-sm text-slate-100 transition-colors focus:border-slate-700 focus:outline-none focus:ring-1 focus:ring-slate-700"
              >
                {CONVERSATION_STATUS_OPTIONS.map(option => (
                  <option key={option} value={option}>
                    {CONVERSATION_STATUS_FILTER_CONFIG[option].label}
                  </option>
                ))}
              </select>
              <ChevronDown className="absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500 pointer-events-none" />
            </div>
          </div>
        )}

        {onRunStatusChange && (
          <div className="flex-1 space-y-1.5">
            <label className="text-xs font-medium text-slate-400">Run Status</label>
            <div className="relative">
              <select
                value={runStatusFilter}
                onChange={e => onRunStatusChange(e.target.value as RunStatusFilter)}
                aria-label="Filter by run status"
                className="w-full appearance-none rounded-lg border border-slate-800 bg-slate-900/50 py-2.5 pl-3 pr-10 text-sm text-slate-100 transition-colors focus:border-slate-700 focus:outline-none focus:ring-1 focus:ring-slate-700"
              >
                {RUN_STATUS_OPTIONS.map(option => (
                  <option key={option} value={option}>
                    {RUN_STATUS_FILTER_CONFIG[option].label}
                  </option>
                ))}
              </select>
              <ChevronDown className="absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500 pointer-events-none" />
            </div>
          </div>
        )}
      </div>

      {/* Desktop: Pill button filters */}
      <div className="hidden md:flex md:flex-wrap md:gap-6">
        {/* Conversation Status */}
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

        {/* Run Status */}
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
