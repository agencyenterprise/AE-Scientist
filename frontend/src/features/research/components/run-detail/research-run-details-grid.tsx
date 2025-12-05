"use client";

import { Calendar } from "lucide-react";
import type { ResearchRunInfo } from "@/types/research";
import { formatDateTime, formatRelativeTime } from "@/shared/lib/date-utils";

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
          <dt className="text-xs text-slate-400">Run ID</dt>
          <dd className="font-mono text-sm text-white">{run.run_id}</dd>
        </div>
        <div>
          <dt className="text-xs text-slate-400">Idea ID</dt>
          <dd className="font-mono text-sm text-white">{run.idea_id}</dd>
        </div>
        <div>
          <dt className="text-xs text-slate-400">Idea Version ID</dt>
          <dd className="font-mono text-sm text-white">{run.idea_version_id}</dd>
        </div>
        <div>
          <dt className="text-xs text-slate-400">Created At</dt>
          <dd className="text-sm text-white">{formatDateTime(run.created_at)}</dd>
        </div>
        <div>
          <dt className="text-xs text-slate-400">Updated At</dt>
          <dd className="text-sm text-white">{formatDateTime(run.updated_at)}</dd>
        </div>
        {run.last_heartbeat_at && (
          <div>
            <dt className="text-xs text-slate-400">Last Heartbeat</dt>
            <dd className="text-sm text-white">{formatRelativeTime(run.last_heartbeat_at)}</dd>
          </div>
        )}
        {run.pod_name && (
          <div>
            <dt className="text-xs text-slate-400">Pod Name</dt>
            <dd className="text-sm text-white">{run.pod_name}</dd>
          </div>
        )}
        {conversationId && (
          <div>
            <dt className="text-xs text-slate-400">Conversation</dt>
            <dd>
              <a
                href={`/conversations/${conversationId}`}
                className="text-sm text-emerald-400 hover:text-emerald-300"
              >
                View Conversation #{conversationId}
              </a>
            </dd>
          </div>
        )}
      </dl>
    </div>
  );
}
