"use client";

import { GitBranch } from "lucide-react";
import { getStatusBadge } from "../utils/research-utils";

export interface ResearchBoardCardHeaderProps {
  displayRunId: string;
  status: string;
  parentRunId?: string | null;
}

export function ResearchBoardCardHeader({
  displayRunId,
  status,
  parentRunId,
}: ResearchBoardCardHeaderProps) {
  return (
    <div className="flex items-center justify-between border-b border-slate-800/50 px-4 py-2.5 sm:px-5 sm:py-3">
      <div className="flex items-center gap-2">
        <span className="font-mono text-xs text-slate-500 sm:text-sm">{displayRunId}</span>
        {parentRunId && (
          <a
            href={`/research/${parentRunId}`}
            className="flex items-center gap-1 text-xs text-emerald-400 hover:text-emerald-300"
            title="Seeded from parent run"
            onClick={e => e.stopPropagation()}
          >
            <GitBranch className="w-3 h-3" />
            <span className="hidden sm:inline">from parent</span>
          </a>
        )}
      </div>
      {getStatusBadge(status, "sm")}
    </div>
  );
}
