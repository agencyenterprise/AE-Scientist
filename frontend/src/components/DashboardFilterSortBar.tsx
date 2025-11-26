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
    <div className="toolbar-glass px-4 sm:px-6 py-2 sticky top-14 z-10">
      <div className="flex items-center justify-between gap-2">
        {/* Filters */}
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={() => setLinearFilter("all")}
            className={`btn-filter ${linearFilter === "all" ? "btn-filter-active" : "btn-filter-inactive"}`}
            title="Show all"
          >
            All
          </button>
          <button
            type="button"
            onClick={() => setLinearFilter("in_progress")}
            className={`btn-filter ${linearFilter === "in_progress" ? "btn-filter-active" : "btn-filter-inactive"}`}
            title="Show in-progress"
          >
            In Progress
          </button>
          <button
            type="button"
            onClick={() => setLinearFilter("completed")}
            className={`btn-filter ${linearFilter === "completed" ? "btn-filter-active" : "btn-filter-inactive"}`}
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
            className="btn-secondary text-xs py-1 px-2"
          >
            {hasQuery && <option value="score">Score</option>}
            <option value="updated">Updated</option>
            <option value="imported">Imported</option>
            <option value="title">Title</option>
          </select>
          <button
            onClick={() => setSortDir(sortDir === "asc" ? "desc" : "asc")}
            className="btn-secondary text-xs py-1 px-2"
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
