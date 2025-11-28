"use client";

import { useEffect } from "react";
import { useDashboard } from "@/features/dashboard/contexts/DashboardContext";
import { ChevronDown, ChevronUp } from "lucide-react";

export function DashboardFilterSortBar({ hasQuery }: { hasQuery: boolean }): React.JSX.Element {
  const { sortKey, setSortKey, sortDir, setSortDir } = useDashboard();

  useEffect(() => {
    if (!hasQuery && sortKey === "score") {
      setSortKey("updated");
    }
  }, [hasQuery, sortKey, setSortKey]);

  return (
    <div className="toolbar-glass px-4 sm:px-6 py-2 sticky top-14 z-10">
      <div className="flex items-center justify-end gap-2">
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
            <ChevronDown className="h-4 w-4" />
          ) : (
            <ChevronUp className="h-4 w-4" />
          )}
        </button>
      </div>
    </div>
  );
}
