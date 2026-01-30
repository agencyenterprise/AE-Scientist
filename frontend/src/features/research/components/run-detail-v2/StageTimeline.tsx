"use client";

import { CheckCircle2, Circle, Loader2 } from "lucide-react";
import { cn } from "@/shared/lib/utils";
import type { StageProgress } from "@/types/research";
import { formatResearchStageName } from "../../utils/research-utils";

interface StageTimelineProps {
  status: string;
  createdAt: string;
  updatedAt: string | null;
  stageProgress: StageProgress[];
}

interface TimelineEvent {
  id: string;
  label: string;
  timestamp: Date;
  status: "completed" | "in_progress" | "pending";
}

function formatTimeAgo(date: Date): string {
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMinutes = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMinutes / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffDays > 0) {
    return `${diffDays}d ago`;
  }
  if (diffHours > 0) {
    return `${diffHours}h ago`;
  }
  if (diffMinutes > 0) {
    return `${diffMinutes}m ago`;
  }
  return "Just now";
}

function buildTimelineEvents(
  status: string,
  createdAt: string,
  updatedAt: string | null,
  stageProgress: StageProgress[]
): TimelineEvent[] {
  const events: TimelineEvent[] = [];

  events.push({
    id: "run_started",
    label: "Run started",
    timestamp: new Date(createdAt),
    status: "completed",
  });

  const stageMap = new Map<string, StageProgress>();

  for (const progress of stageProgress) {
    const stageNumber = progress.stage.split("_")[0];
    const existing = stageMap.get(stageNumber ?? "0") ?? undefined;

    if (!existing || progress.iteration > existing.iteration) {
      stageMap.set(stageNumber ?? "0", progress);
    }
  }

  const stages = Array.from(stageMap.entries()).sort(([a], [b]) => parseInt(a) - parseInt(b));

  const runIsFinished = status === "completed" || status === "failed";
  const highestStageNumber =
    stages.length > 0 ? Number(stages[stages.length - 1]?.toString() ?? 0) : 0;

  for (const [stageNumber, progress] of stages) {
    const stageNum = Number(stageNumber);

    const isCompleted =
      runIsFinished ||
      progress.iteration >= progress.max_iterations ||
      stageNum < highestStageNumber;

    const isActive = !isCompleted && status === "running";

    events.push({
      id: `stage_${stageNumber}`,
      label: formatResearchStageName(progress.stage) ?? progress.stage,
      timestamp: new Date(progress.created_at),
      status: isCompleted ? "completed" : isActive ? "in_progress" : "pending",
    });
  }

  if (status === "completed" && updatedAt) {
    events.push({
      id: "run_completed",
      label: "Run completed",
      timestamp: new Date(updatedAt),
      status: "completed",
    });
  }

  if (status === "failed" && updatedAt) {
    events.push({
      id: "run_failed",
      label: "Run failed",
      timestamp: new Date(updatedAt),
      status: "completed",
    });
  }

  return events;
}

export function StageTimeline({ status, createdAt, updatedAt, stageProgress }: StageTimelineProps) {
  const events = buildTimelineEvents(status, createdAt, updatedAt, stageProgress);

  if (events.length === 0) {
    return null;
  }

  return (
    <div className="rounded-lg border border-border bg-card p-6">
      <h3 className="text-base font-semibold text-foreground mb-6">Timeline</h3>

      <div className="relative">
        {events.map((event, index) => {
          const isLast = index === events.length - 1;

          return (
            <div key={event.id} className="relative flex gap-4">
              {!isLast && (
                <div
                  className={cn(
                    "absolute left-[11px] top-6 w-0.5 h-full -mb-2",
                    event.status === "completed" ? "bg-emerald-500/50" : "bg-border"
                  )}
                />
              )}

              <div className="relative z-10 shrink-0">
                {event.status === "completed" ? (
                  <CheckCircle2 className="h-6 w-6 text-emerald-500" />
                ) : event.status === "in_progress" ? (
                  <Loader2 className="h-6 w-6 text-yellow-500 animate-spin" />
                ) : (
                  <Circle className="h-6 w-6 text-muted-foreground" />
                )}
              </div>

              <div className={cn("pb-6", isLast && "pb-0")}>
                <p
                  className={cn(
                    "text-sm font-medium",
                    event.status === "completed" ? "text-foreground" : "text-muted-foreground"
                  )}
                >
                  {event.label}
                </p>
                <p className="text-xs text-muted-foreground">{formatTimeAgo(event.timestamp)}</p>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
