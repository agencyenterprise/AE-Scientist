"use client";

import { FlaskConical } from "lucide-react";

/**
 * Empty state component shown when user has no research history.
 */
export function ResearchHistoryEmpty() {
  return (
    <div className="flex flex-col items-center justify-center py-8 text-center">
      <FlaskConical className="mb-3 h-10 w-10 text-slate-600" />
      <h3 className="text-base font-medium text-slate-300">No research history yet</h3>
      <p className="mt-1 text-sm text-slate-500">
        Submit your first hypothesis above to get started
      </p>
    </div>
  );
}
