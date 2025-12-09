"use client";

import { Search, Lightbulb } from "lucide-react";
import type { IdeationQueueHeaderProps } from "../types/ideation-queue.types";

/**
 * Header component for the Ideation Queue page
 * Includes title, count, and search input
 */
export function IdeationQueueHeader({
  searchTerm,
  onSearchChange,
  totalCount,
  filteredCount,
}: IdeationQueueHeaderProps) {
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
    </div>
  );
}
