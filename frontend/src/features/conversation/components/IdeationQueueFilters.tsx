"use client";

import { cn } from "@/shared/lib/utils";
import type { IdeationQueueFiltersProps } from "../types/ideation-queue.types";
import { STATUS_FILTER_OPTIONS, STATUS_FILTER_CONFIG } from "../utils/ideation-queue-utils";

/**
 * Status filter buttons for the Ideation Queue
 * Follows the LOG_FILTER_CONFIG pattern from research-logs-list.tsx
 */
export function IdeationQueueFilters({ activeFilter, onFilterChange }: IdeationQueueFiltersProps) {
  return (
    <div className="flex items-center gap-1" role="group" aria-label="Status filter">
      {STATUS_FILTER_OPTIONS.map(option => (
        <button
          key={option}
          type="button"
          onClick={() => onFilterChange(option)}
          aria-pressed={activeFilter === option}
          className={cn(
            "rounded-md px-3 py-1 text-xs font-medium transition-colors",
            activeFilter === option
              ? STATUS_FILTER_CONFIG[option].activeClass
              : "text-slate-500 hover:bg-slate-800 hover:text-slate-300"
          )}
        >
          {STATUS_FILTER_CONFIG[option].label}
        </button>
      ))}
    </div>
  );
}
