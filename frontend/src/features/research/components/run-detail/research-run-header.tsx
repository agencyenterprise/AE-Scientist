"use client";

import { ArrowLeft, ExternalLink, Loader2, Sprout, StopCircle } from "lucide-react";
import { useRouter } from "next/navigation";
import { formatRelativeTime } from "@/shared/lib/date-utils";
import { getStatusBadge } from "../../utils/research-utils";
import { Button } from "@/shared/components/ui/button";

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
  conversationId: number | null;
  onSeedNewIdea?: () => void;
  seedPending?: boolean;
  seedError?: string | null;
}

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
  conversationId,
  onSeedNewIdea,
  seedPending = false,
  seedError = null,
}: ResearchRunHeaderProps) {
  const router = useRouter();

  const canSeedIdea = status === "completed" && conversationId !== null;

  return (
    <div className="sticky top-0 z-20 -mx-6 -mt-6 mb-4 border-b border-border bg-background/95 px-6 py-4 backdrop-blur-sm">
      <div className="flex items-center gap-4">
        <Button
          variant="outline"
          size="icon-sm"
          onClick={() => router.push("/research")}
          aria-label="Back to Research Runs"
        >
          <ArrowLeft className="h-4 w-4" />
        </Button>

        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="truncate text-lg font-semibold text-foreground" title={title}>
              {title}
            </h1>

            <div className="flex items-center gap-2">
              {getStatusBadge(status, "sm")}

              {(terminationStatus === "requested" || terminationStatus === "in_progress") && (
                <span className="inline-flex items-center rounded-full border border-amber-500/40 bg-amber-500/10 px-2 py-0.5 text-xs font-medium text-amber-200">
                  Terminating
                </span>
              )}
              {terminationStatus === "terminated" && (
                <span className="inline-flex items-center rounded-full border border-muted bg-muted px-2 py-0.5 text-xs font-medium text-muted-foreground">
                  Terminated
                </span>
              )}
              {terminationStatus === "failed" && (
                <span className="inline-flex items-center rounded-full border border-destructive/40 bg-destructive/10 px-2 py-0.5 text-xs font-medium text-destructive">
                  Termination failed
                </span>
              )}
            </div>
          </div>

          <p className="mt-0.5 text-sm text-muted-foreground">
            {runNumber ? `Run ${runNumber}` : "Run"} · Created {formatRelativeTime(createdAt)}
          </p>
        </div>

        <div className="flex flex-shrink-0 items-center gap-2">
          {conversationId && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => router.push(`/conversations/${conversationId}`)}
            >
              <ExternalLink className="h-4 w-4" />
              <span className="hidden sm:inline">View Idea</span>
            </Button>
          )}

          {canSeedIdea && onSeedNewIdea && (
            <Button
              variant="outline"
              size="sm"
              onClick={onSeedNewIdea}
              disabled={seedPending}
              className="border-emerald-500/40 text-emerald-400 hover:bg-emerald-500/10"
            >
              {seedPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Sprout className="h-4 w-4" />
              )}
              <span className="hidden sm:inline">
                {seedPending ? "Seeding..." : "Seed New Idea"}
              </span>
            </Button>
          )}

          {canStopRun && (
            <Button
              variant="outline"
              size="sm"
              onClick={onStopRun}
              disabled={stopPending}
              className="border-destructive/40 text-destructive hover:bg-destructive/10"
            >
              {stopPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <StopCircle className="h-4 w-4" />
              )}
              <span className="hidden sm:inline">{stopPending ? "Stopping..." : "Stop"}</span>
            </Button>
          )}
        </div>
      </div>

      {(stopError || seedError) && (
        <div className="mt-2">
          {stopError && (
            <p className="text-sm text-destructive" role="alert">
              {stopError}
            </p>
          )}
          {seedError && (
            <p className="text-sm text-destructive" role="alert">
              {seedError}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
