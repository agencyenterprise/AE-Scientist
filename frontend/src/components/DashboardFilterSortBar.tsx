"use client";

import { useEffect } from "react";
import { useDashboard } from "@/app/(dashboard)/DashboardContext";

export function DashboardFilterSortBar({ hasQuery }: { hasQuery: boolean }): React.JSX.Element {
  const { linearFilter, setLinearFilter, sortKey, setSortKey, sortDir, setSortDir } =
    useDashboard();

  useEffect(() => {
    if (!hasQuery && sortKey === "score") {
      setSortKey("updated");
    }
  }, [hasQuery, sortKey, setSortKey]);

  return (
    <div className="px-4 sm:px-6 py-2 border-b border-[var(--border)] bg-[color-mix(in_srgb,var(--surface),transparent_25%)] backdrop-blur supports-[backdrop-filter]:bg-[color-mix(in_srgb,var(--surface),transparent_35%)] sticky top-[56px] md:top-[56px] z-10">
      <div className="flex items-center justify-between gap-2">
        {/* Filters */}
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={() => setLinearFilter("all")}
            className={`px-2 py-1 text-[11px] rounded border ${
              linearFilter === "all"
                ? "bg-[var(--foreground)] text-[var(--background)] border-[var(--foreground)]"
                : "bg-[var(--surface)] text-[var(--foreground)]/80 border-[var(--border)] hover:bg-[var(--muted)]"
            }`}
            title="Show all"
          >
            All
          </button>
          <button
            type="button"
            onClick={() => setLinearFilter("in_progress")}
            className={`px-2 py-1 text-[11px] rounded border ${
              linearFilter === "in_progress"
                ? "bg-[var(--foreground)] text-[var(--background)] border-[var(--foreground)]"
                : "bg-[var(--surface)] text-[var(--foreground)]/80 border-[var(--border)] hover:bg-[var(--muted)]"
            }`}
            title="Show in-progress"
          >
            In Progress
          </button>
          <button
            type="button"
            onClick={() => setLinearFilter("completed")}
            className={`px-2 py-1 text-[11px] rounded border ${
              linearFilter === "completed"
                ? "bg-[var(--foreground)] text-[var(--background)] border-[var(--foreground)]"
                : "bg-[var(--surface)] text-[var(--foreground)]/80 border-[var(--border)] hover:bg-[var(--muted)]"
            }`}
            title="Show completed"
          >
            Completed
          </button>
        </div>

        {/* Sorting */}
        <div className="flex items-center gap-2">
          <select
            value={sortKey}
            onChange={e => {
              const val = e.target.value as typeof sortKey;
              setSortKey(val);
              if (val === "score") setSortDir("desc");
            }}
            className="text-xs border border-gray-300 rounded-md py-1 px-2 bg-white shadow-sm"
          >
            {hasQuery && <option value="score">Score</option>}
            <option value="updated">Updated</option>
            <option value="imported">Imported</option>
            <option value="title">Title</option>
          </select>
          <button
            onClick={() => setSortDir(sortDir === "asc" ? "desc" : "asc")}
            className="text-xs border border-gray-300 rounded-md py-1 px-2 bg-white shadow-sm"
            title="Toggle sort direction"
          >
            {sortDir === "desc" ? (
              <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M19 9l-7 7-7-7"
                />
              </svg>
            ) : (
              <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M5 15l7-7 7 7"
                />
              </svg>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
