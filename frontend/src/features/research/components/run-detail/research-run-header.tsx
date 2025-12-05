"use client";

import { ArrowLeft, Loader2, StopCircle, Wifi, WifiOff } from "lucide-react";
import { useRouter } from "next/navigation";
import { formatRelativeTime } from "@/shared/lib/date-utils";
import { getStatusBadge } from "../../utils/research-utils";

interface ResearchRunHeaderProps {
  runId: string;
  status: string;
  createdAt: string;
  isConnected: boolean;
  connectionError: string | null;
  canStopRun: boolean;
  stopPending: boolean;
  stopError: string | null;
  onStopRun: () => void;
  onReconnect: () => void;
}

/**
 * Header component for research run detail page
 */
export function ResearchRunHeader({
  runId,
  status,
  createdAt,
  isConnected,
  connectionError,
  canStopRun,
  stopPending,
  stopError,
  onStopRun,
  onReconnect,
}: ResearchRunHeaderProps) {
  const router = useRouter();
  const isLive = status === "running" || status === "pending";

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
          <h1 className="text-2xl font-semibold text-white">{runId}</h1>
          {getStatusBadge(status, "lg")}
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
          {isLive && (
            <>
              {isConnected ? (
                <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-500/15 px-3 py-1 text-xs font-medium text-emerald-400">
                  <Wifi className="h-3 w-3" />
                  Live
                </span>
              ) : connectionError ? (
                <button
                  onClick={onReconnect}
                  className="inline-flex items-center gap-1.5 rounded-full bg-amber-500/15 px-3 py-1 text-xs font-medium text-amber-400 transition-colors hover:bg-amber-500/25"
                >
                  <WifiOff className="h-3 w-3" />
                  Reconnect
                </button>
              ) : null}
            </>
          )}
        </div>
        <p className="mt-1 text-sm text-slate-400">Created {formatRelativeTime(createdAt)}</p>
        {stopError && (
          <p className="mt-2 text-sm text-red-400" role="alert">
            {stopError}
          </p>
        )}
      </div>
    </div>
  );
}
