"use client";

import Link from "next/link";
import { Eye, ArrowRight, Package, User } from "lucide-react";

export interface ResearchBoardCardFooterProps {
  runId: string;
  createdByName: string;
  createdAt: string;
  artifactsCount: number;
}

export function ResearchBoardCardFooter({
  runId,
  createdByName,
  createdAt,
  artifactsCount,
}: ResearchBoardCardFooterProps) {
  return (
    <div className="flex items-center justify-between border-t border-slate-800/50 px-5 py-3">
      <div className="flex items-center gap-4 text-sm text-slate-400">
        <div className="flex items-center gap-1.5">
          <User className="h-4 w-4" />
          <span>{createdByName}</span>
        </div>
        <span>•</span>
        <span>{createdAt}</span>
        {artifactsCount > 0 && (
          <>
            <span>•</span>
            <div className="flex items-center gap-1.5">
              <Package className="h-4 w-4" />
              <span>
                {artifactsCount} artifact{artifactsCount !== 1 ? "s" : ""}
              </span>
            </div>
          </>
        )}
      </div>

      <Link
        href={`/research/${runId}`}
        className="inline-flex items-center gap-2 rounded-lg bg-emerald-500/15 px-4 py-2 text-sm font-medium text-emerald-400 transition-colors hover:bg-emerald-500/25"
      >
        <Eye className="h-4 w-4" />
        View Details
        <ArrowRight className="h-4 w-4" />
      </Link>
    </div>
  );
}
