"use client";

import { Calendar } from "lucide-react";
import type { ResearchRunInfo } from "@/types/research";
import { formatDateTime, formatDuration } from "@/shared/lib/date-utils";

interface ResearchRunDetailsGridProps {
  run: ResearchRunInfo;
  conversationId: number | null;
}

/**
 * Run details grid showing metadata like IDs, timestamps, and pod info
 */
export function ResearchRunDetailsGrid({ run, conversationId }: ResearchRunDetailsGridProps) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/50 w-full p-6">
      <div className="mb-4 flex items-center gap-2">
        <Calendar className="h-5 w-5 text-slate-400" />
        <h2 className="text-lg font-semibold text-white">Run Details</h2>
      </div>
      <dl className="grid gap-4 sm:grid-cols-2">
        <div>
          <dt className="text-xs text-slate-400">Started at</dt>
          <dd className="text-sm text-white">{formatDateTime(run.created_at)}</dd>
        </div>
        <div>
          <dt className="text-xs text-slate-400">Run duration</dt>
          <dd className="text-sm text-white">{formatDuration(run.created_at, run.updated_at)}</dd>
        </div>
        <div>
          <dt className="text-xs text-slate-400">Completed at</dt>
          <dd className="text-sm text-white">
            {run.status === "running" || run.status === "initializing" || run.status === "pending"
              ? "In Progress"
              : formatDateTime(run.updated_at)}
          </dd>
        </div>
        {conversationId && (
          <div>
            <dt className="text-xs text-slate-400">Idea</dt>
            <dd>
              <a
                href={`/conversations/${conversationId}`}
                className="text-sm text-emerald-400 hover:text-emerald-300"
              >
                View Idea
              </a>
            </dd>
          </div>
        )}
      </dl>
    </div>
  );
}
