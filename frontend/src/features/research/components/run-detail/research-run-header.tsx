"use client";

import { ArrowLeft, BookOpen, Loader2, StopCircle } from "lucide-react";
import { useRouter, useParams } from "next/navigation";
import { formatRelativeTime } from "@/shared/lib/date-utils";
import { getStatusBadge } from "../../utils/research-utils";

interface ResearchRunHeaderProps {
  title: string;
  runNumber: number | null;
  status: string;
  terminationStatus: string;
  createdAt: string;
  canStopRun: boolean;
  stopPending: boolean;
  stopError: string | null;
  onStopRun: () => void;
}

/**
 * Header component for research run detail page
 */
export function ResearchRunHeader({
  title,
  runNumber,
  status,
  terminationStatus,
  createdAt,
  canStopRun,
  stopPending,
  stopError,
  onStopRun,
}: ResearchRunHeaderProps) {
  const router = useRouter();
  const params = useParams();
  const runId = params?.runId as string;

  return (
    <div className="flex items-center gap-4">
      <button
        onClick={() => router.push("/research")}
        className="flex h-10 w-10 items-center justify-center rounded-lg border border-slate-700 bg-slate-900/50 text-slate-400 transition-colors hover:bg-slate-800 hover:text-white"
      >
        <ArrowLeft className="h-5 w-5" />
      </button>
      <div className="flex-1">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-semibold text-white max-w-3xl">{title}</h1>
          {getStatusBadge(status, "lg")}
          {(terminationStatus === "requested" || terminationStatus === "in_progress") && (
            <span className="inline-flex items-center rounded-full border border-amber-500/40 bg-amber-500/10 px-3 py-1 text-sm font-medium text-amber-200">
              Terminating
            </span>
          )}
          {terminationStatus === "terminated" && (
            <span className="inline-flex items-center rounded-full border border-slate-500/40 bg-slate-500/10 px-3 py-1 text-sm font-medium text-slate-200">
              Terminated
            </span>
          )}
          {terminationStatus === "failed" && (
            <span className="inline-flex items-center rounded-full border border-red-500/40 bg-red-500/10 px-3 py-1 text-sm font-medium text-red-200">
              Termination failed
            </span>
          )}
          <button
            onClick={() => router.push(`/research/${runId}/narrative`)}
            className="inline-flex items-center gap-2 rounded-full border border-emerald-500/40 px-3 py-2 text-sm font-medium text-emerald-200 transition-colors hover:bg-emerald-500/10"
          >
            <BookOpen className="h-4 w-4" />
            Narrative View
            <span className="ml-1 rounded bg-emerald-500/20 px-1.5 py-0.5 text-xs font-semibold text-emerald-300 ring-1 ring-emerald-500/30">
              BETA
            </span>
          </button>
          {canStopRun && (
            <button
              onClick={onStopRun}
              disabled={stopPending}
              className="inline-flex items-center gap-2 rounded-lg border border-red-500/40 px-3 py-1.5 text-sm font-medium text-red-200 transition-colors hover:bg-red-500/10 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {stopPending ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Stopping...
                </>
              ) : (
                <>
                  <StopCircle className="h-4 w-4" />
                  Stop Run
                </>
              )}
            </button>
          )}
        </div>
        <p className="mt-1 text-sm text-slate-400">
          {runNumber ? `Run ${runNumber} • ` : ""}
          Created {formatRelativeTime(createdAt)}
        </p>

        {stopError && (
          <p className="mt-2 text-sm text-red-400" role="alert">
            {stopError}
          </p>
        )}
      </div>
    </div>
  );
}
