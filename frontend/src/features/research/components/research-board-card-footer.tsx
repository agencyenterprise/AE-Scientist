"use client";

import Link from "next/link";
import { Eye, ArrowRight, Package } from "lucide-react";

export interface ResearchBoardCardFooterProps {
  runId: string;
  createdAt: string;
  artifactsCount: number;
}

export function ResearchBoardCardFooter({
  runId,
  createdAt,
  artifactsCount,
}: ResearchBoardCardFooterProps) {
  return (
    <div className="flex flex-col gap-3 border-t border-slate-800/50 px-4 py-3 sm:flex-row sm:items-center sm:justify-between sm:px-5">
      <div className="flex flex-wrap items-center gap-4 text-sm text-slate-400">
        <span>{createdAt}</span>
        {artifactsCount > 0 && (
          <div className="flex items-center gap-1.5">
            <Package className="h-4 w-4" />
            <span>
              {artifactsCount} artifact{artifactsCount !== 1 ? "s" : ""}
            </span>
          </div>
        )}
      </div>

      <Link
        href={`/research/${runId}`}
        className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-emerald-500/15 px-4 py-2 text-sm font-medium text-emerald-400 transition-colors hover:bg-emerald-500/25 sm:w-auto sm:justify-start"
      >
        <Eye className="h-4 w-4" />
        View Details
        <ArrowRight className="h-4 w-4" />
      </Link>
    </div>
  );
}
