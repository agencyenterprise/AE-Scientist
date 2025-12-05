"use client";

import { getStatusBadge } from "../utils/research-utils";

export interface ResearchBoardCardHeaderProps {
  displayRunId: string;
  status: string;
}

export function ResearchBoardCardHeader({ displayRunId, status }: ResearchBoardCardHeaderProps) {
  return (
    <div className="flex items-center justify-between border-b border-slate-800/50 px-5 py-3">
      <span className="font-mono text-sm text-slate-500">{displayRunId}</span>
      {getStatusBadge(status)}
    </div>
  );
}
