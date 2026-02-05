"use client";

import { CostDetailsCard } from "../CostDetailsCard";
import type { ResearchRunCostResponse } from "@/types";
import type { ResearchRunInfo } from "@/types/research";
import { Info } from "lucide-react";
import { formatRelativeTime } from "@/shared/lib/date-utils";

interface RunCostTabProps {
  run: ResearchRunInfo;
  conversationId: number | null;
  costDetails: ResearchRunCostResponse | null;
  isLoadingCost: boolean;
  hwEstimatedCostCents: number | null;
  hwCostPerHourCents: number | null;
  hwActualCostCents: number | null;
}

export function RunCostTab({
  run,
  costDetails,
  isLoadingCost,
  hwEstimatedCostCents,
  hwCostPerHourCents,
  hwActualCostCents,
}: RunCostTabProps) {
  const startTime = new Date(run.created_at);
  const endTime = run.updated_at ? new Date(run.updated_at) : new Date();
  const durationMs = endTime.getTime() - startTime.getTime();
  const durationMinutes = Math.floor(durationMs / 60000);
  const durationHours = Math.floor(durationMinutes / 60);
  const remainingMinutes = durationMinutes % 60;

  const formatDuration = () => {
    if (durationHours > 0) {
      return `${durationHours}h ${remainingMinutes}m`;
    }
    return `${durationMinutes}m`;
  };

  return (
    <div className="flex flex-col gap-6">
      <CostDetailsCard
        cost={costDetails}
        isLoading={isLoadingCost}
        hwEstimatedCostCents={hwEstimatedCostCents}
        hwCostPerHourCents={hwCostPerHourCents}
        hwActualCostCents={hwActualCostCents}
      />

      <div className="rounded-2xl border border-slate-800 bg-slate-900/50 w-full p-6">
        <div className="mb-4 flex items-center gap-2">
          <Info className="h-5 w-5 text-slate-400" />
          <h2 className="text-lg font-semibold text-white">Run Details</h2>
        </div>
        <dl className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <div>
            <dt className="text-xs text-slate-400">Started at</dt>
            <dd className="font-mono text-sm text-white">
              {new Date(run.created_at).toLocaleString()}
            </dd>
            <dd className="text-xs text-slate-400">{formatRelativeTime(run.created_at)}</dd>
          </div>
          {run.updated_at && (
            <div>
              <dt className="text-xs text-slate-400">
                {run.status === "completed" || run.status === "failed"
                  ? "Completed at"
                  : "Updated at"}
              </dt>
              <dd className="font-mono text-sm text-white">
                {new Date(run.updated_at).toLocaleString()}
              </dd>
              <dd className="text-xs text-slate-400">{formatRelativeTime(run.updated_at)}</dd>
            </div>
          )}
          <div>
            <dt className="text-xs text-slate-400">Duration</dt>
            <dd className="font-mono text-lg text-white">{formatDuration()}</dd>
          </div>
          <div>
            <dt className="text-xs text-slate-400">GPU Type</dt>
            <dd className="font-mono text-sm text-white">{run.gpu_type || "—"}</dd>
          </div>
        </dl>
      </div>
    </div>
  );
}
