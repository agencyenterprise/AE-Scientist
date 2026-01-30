"use client";

import { useEffect, useRef, useState, useCallback, useMemo } from "react";
import { ScrollArea } from "@/shared/components/ui/scroll-area";
import { config } from "@/shared/lib/config";
import { withAuthHeaders } from "@/shared/lib/session-token";
import { cn } from "@/shared/lib/utils";
import {
  Play,
  Flag,
  Layers,
  CheckCircle2,
  RefreshCw,
  Cpu,
  FileText,
  AlertCircle,
  Loader2,
  ChevronRight,
} from "lucide-react";
import type { components } from "@/types/api.gen";

type ResearchRunState = components["schemas"]["ResearchRunState"];
type TimelineEvent = NonNullable<ResearchRunState["timeline"]>[number];

interface ResearchActivityFeedProps {
  runId: string;
  maxHeight?: string;
}

interface ParsedSseFrame {
  event: string;
  data: string;
}

interface StageGroup {
  stageId: string;
  stageName: string;
  status: "completed" | "in_progress" | "pending";
  events: TimelineEvent[];
  progress: number;
  startTime: string | null;
  endTime: string | null;
}

function parseSseFrame(text: string): ParsedSseFrame | null {
  const lines = text.split("\n");
  let event = "";
  let data = "";

  for (const line of lines) {
    if (line.startsWith("event:")) {
      event = line.slice(6).trim();
    } else if (line.startsWith("data:")) {
      data = line.slice(5).trim();
    }
  }

  if (event && data) {
    return { event, data };
  }
  return null;
}

function getEventStage(event: TimelineEvent): string {
  if ("stage" in event && event.stage) {
    return event.stage as string;
  }
  if (event.type === "run_started") return "_run_start";
  if (event.type === "run_finished") return "_run_end";
  return "_unknown";
}

function getStageName(stageId: string): string {
  if (stageId === "_run_start") return "Run Initialization";
  if (stageId === "_run_end") return "Run Completion";
  if (stageId === "_unknown") return "Other Events";

  const parts = stageId.split("_");
  if (parts.length > 1 && !Number.isNaN(Number(parts[0]))) {
    return parts
      .slice(1)
      .map(word => word.charAt(0).toUpperCase() + word.slice(1))
      .join(" ");
  }

  return stageId
    .split("_")
    .map(word => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

function groupEventsByStage(events: TimelineEvent[]): StageGroup[] {
  const stageMap = new Map<string, TimelineEvent[]>();
  const stageOrder: string[] = [];

  for (const event of events) {
    const stageId = getEventStage(event);

    if (!stageMap.has(stageId)) {
      stageMap.set(stageId, []);
      stageOrder.push(stageId);
    }
    stageMap.get(stageId)!.push(event);
  }

  return stageOrder.map(stageId => {
    const stageEvents = stageMap.get(stageId) || [];

    const isRunStartStage = stageId === "_run_start";
    const isRunEndStage = stageId === "_run_end";

    const hasRunStarted = stageEvents.some(e => e.type === "run_started");
    const hasRunFinished = stageEvents.some(e => e.type === "run_finished");
    const hasStageCompleted = stageEvents.some(e => e.type === "stage_completed");
    const hasStageStarted = stageEvents.some(e => e.type === "stage_started");

    let isCompleted = false;
    if (isRunStartStage) {
      isCompleted = hasRunStarted;
    } else if (isRunEndStage) {
      isCompleted = hasRunFinished;
    } else {
      isCompleted = hasStageCompleted;
    }

    const hasStarted = hasStageStarted || hasRunStarted;

    const progressEvents = stageEvents.filter(e => e.type === "progress_update");
    const lastProgress = progressEvents.length > 0 ? progressEvents[progressEvents.length - 1] : null;
    let progress = 0;
    if (isCompleted) {
      progress = 100;
    } else if (lastProgress && "iteration" in lastProgress && "max_iterations" in lastProgress) {
      progress = Math.round(((lastProgress.iteration as number) / (lastProgress.max_iterations as number)) * 100);
    } else if (hasStarted) {
      progress = 10; // Just started
    }

    const timestamps = stageEvents.map(e => new Date(e.timestamp).getTime());
    const startTime = timestamps.length > 0 ? new Date(Math.min(...timestamps)).toISOString() : null;
    const endTime = isCompleted && timestamps.length > 0 ? new Date(Math.max(...timestamps)).toISOString() : null;

    return {
      stageId,
      stageName: getStageName(stageId),
      status: isCompleted ? "completed" : hasStarted ? "in_progress" : "pending",
      events: stageEvents,
      progress,
      startTime,
      endTime,
    };
  });
}

function formatDuration(startTime: string | null, endTime: string | null): string {
  if (!startTime) return "";

  const start = new Date(startTime);
  const end = endTime ? new Date(endTime) : new Date();
  const diffMs = end.getTime() - start.getTime();
  const diffMinutes = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMinutes / 60);

  if (diffHours > 0) {
    const remainingMinutes = diffMinutes % 60;
    return remainingMinutes > 0 ? `${diffHours}h ${remainingMinutes}m` : `${diffHours}h`;
  }
  return `${diffMinutes}m`;
}

function formatTimeAgo(timestamp: string): string {
  const date = new Date(timestamp);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMinutes = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMinutes / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffDays > 0) return `${diffDays}d ago`;
  if (diffHours > 0) return `${diffHours}h ago`;
  if (diffMinutes > 0) return `${diffMinutes}m ago`;
  return "Just now";
}

function getEventIcon(type: string) {
  switch (type) {
    case "run_started":
      return <Play className="h-3.5 w-3.5" />;
    case "stage_started":
      return <Layers className="h-3.5 w-3.5" />;
    case "stage_completed":
      return <CheckCircle2 className="h-3.5 w-3.5" />;
    case "progress_update":
      return <RefreshCw className="h-3.5 w-3.5" />;
    case "node_result":
    case "node_execution_started":
    case "node_execution_completed":
      return <Cpu className="h-3.5 w-3.5" />;
    case "paper_generation_step":
      return <FileText className="h-3.5 w-3.5" />;
    case "run_finished":
      return <Flag className="h-3.5 w-3.5" />;
    default:
      return <AlertCircle className="h-3.5 w-3.5" />;
  }
}

function getEventColor(type: string) {
  switch (type) {
    case "run_started":
    case "stage_completed":
    case "run_finished":
      return "text-emerald-400";
    case "stage_started":
      return "text-blue-400";
    case "progress_update":
      return "text-yellow-400";
    case "node_result":
      return "text-purple-400";
    case "node_execution_started":
    case "node_execution_completed":
      return "text-cyan-400";
    case "paper_generation_step":
      return "text-orange-400";
    default:
      return "text-slate-400";
  }
}

function getEventLabel(type: string) {
  switch (type) {
    case "run_started":
      return "Run Started";
    case "stage_started":
      return "Stage Started";
    case "stage_completed":
      return "Stage Completed";
    case "progress_update":
      return "Progress Update";
    case "node_result":
      return "Node Result";
    case "node_execution_started":
      return "Execution Started";
    case "node_execution_completed":
      return "Execution Complete";
    case "paper_generation_step":
      return "Paper Generation";
    case "run_finished":
      return "Run Finished";
    default:
      return type.replace(/_/g, " ");
  }
}

function CompactEventItem({ event }: { event: TimelineEvent }) {
  const icon = getEventIcon(event.type);
  const colorClass = getEventColor(event.type);
  const label = getEventLabel(event.type);

  return (
    <div className="flex items-start gap-3 py-2 px-3 rounded-md hover:bg-muted/30 transition-colors">
      <div className={cn("mt-0.5 shrink-0", colorClass)}>{icon}</div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between gap-2">
          <span className={cn("text-sm font-medium", colorClass)}>{label}</span>
          <span className="text-xs text-muted-foreground shrink-0">
            {formatTimeAgo(event.timestamp)}
          </span>
        </div>
        {event.headline && (
          <p className="text-xs text-muted-foreground mt-0.5 line-clamp-1">{event.headline}</p>
        )}
        <EventDetails event={event} />
      </div>
    </div>
  );
}

function EventDetails({ event }: { event: TimelineEvent }) {
  switch (event.type) {
    case "run_started":
      return "gpu_type" in event && event.gpu_type ? (
        <p className="text-xs text-muted-foreground mt-0.5">GPU: {event.gpu_type}</p>
      ) : null;

    case "progress_update":
      return "iteration" in event && "max_iterations" in event ? (
        <p className="text-xs text-muted-foreground mt-0.5">
          Iteration {event.iteration}/{event.max_iterations}
        </p>
      ) : null;

    case "node_result":
      return "outcome" in event && event.outcome ? (
        <p className="text-xs text-muted-foreground mt-0.5">Outcome: {event.outcome}</p>
      ) : null;

    case "run_finished":
      return "status" in event && event.status ? (
        <span
          className={cn(
            "inline-block mt-1 px-1.5 py-0.5 rounded text-xs font-medium",
            event.success ? "bg-emerald-500/20 text-emerald-400" : "bg-red-500/20 text-red-400"
          )}
        >
          {event.status.toUpperCase()}
        </span>
      ) : null;

    default:
      return null;
  }
}

function StageSection({
  stage,
  isExpanded,
  onToggle,
}: {
  stage: StageGroup;
  isExpanded: boolean;
  onToggle: () => void;
}) {
  const statusBadge = {
    completed: (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-emerald-500/20 text-emerald-400">
        <CheckCircle2 className="h-3 w-3" />
        Completed
      </span>
    ),
    in_progress: (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-yellow-500/20 text-yellow-400">
        <Loader2 className="h-3 w-3 animate-spin" />
        In Progress
      </span>
    ),
    pending: (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-slate-500/20 text-slate-400">
        Pending
      </span>
    ),
  };

  const duration = formatDuration(stage.startTime, stage.endTime);

  return (
    <div className="border border-border rounded-lg overflow-hidden">
      <button
        onClick={onToggle}
        className="w-full flex items-center justify-between gap-4 p-4 hover:bg-muted/30 transition-colors text-left"
      >
        <div className="flex items-center gap-3 min-w-0">
          <ChevronRight
            className={cn(
              "h-4 w-4 text-muted-foreground shrink-0 transition-transform",
              isExpanded && "rotate-90"
            )}
          />
          <div className="min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="font-semibold text-foreground">{stage.stageName}</span>
              {statusBadge[stage.status]}
            </div>
            <p className="text-xs text-muted-foreground mt-0.5">
              {stage.events.length} event{stage.events.length !== 1 ? "s" : ""}
              {duration && ` • ${duration}`}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3 shrink-0">
          <span className="text-sm font-medium text-foreground">{stage.progress}%</span>
          <div className="w-20 h-1.5 bg-muted rounded-full overflow-hidden">
            <div
              className={cn(
                "h-full rounded-full transition-all",
                stage.status === "completed"
                  ? "bg-emerald-500"
                  : stage.status === "in_progress"
                    ? "bg-yellow-500"
                    : "bg-slate-500"
              )}
              style={{ width: `${stage.progress}%` }}
            />
          </div>
        </div>
      </button>

      {isExpanded && (
        <div className="border-t border-border bg-muted/10">
          <div className="divide-y divide-border/50">
            {stage.events.map((event, idx) => (
              <CompactEventItem key={event.id || idx} event={event} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export function ResearchActivityFeed({ runId, maxHeight = "500px" }: ResearchActivityFeedProps) {
  const [events, setEvents] = useState<TimelineEvent[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedStages, setExpandedStages] = useState<Set<string>>(new Set());
  const abortControllerRef = useRef<AbortController | null>(null);
  const scrollAreaRef = useRef<HTMLDivElement>(null);

  const stageGroups = useMemo(() => groupEventsByStage(events), [events]);

  useEffect(() => {
    const inProgressStage = stageGroups.find(s => s.status === "in_progress");
    if (inProgressStage && !expandedStages.has(inProgressStage.stageId)) {
      setExpandedStages(prev => new Set([...prev, inProgressStage.stageId]));
    }
  }, [stageGroups, expandedStages]);

  const toggleStage = useCallback((stageId: string) => {
    setExpandedStages(prev => {
      const next = new Set(prev);
      if (next.has(stageId)) {
        next.delete(stageId);
      } else {
        next.add(stageId);
      }
      return next;
    });
  }, []);

  const connectToStream = useCallback(async () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }

    abortControllerRef.current = new AbortController();
    setIsLoading(true);
    setError(null);

    try {
      const response = await fetch(`${config.apiUrl}/research-runs/${runId}/narrative-stream`, {
        headers: withAuthHeaders(new Headers({ Accept: "text/event-stream" })),
        signal: abortControllerRef.current.signal,
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      if (!response.body) {
        throw new Error("No response body");
      }

      setIsConnected(true);
      setIsLoading(false);

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const frames = buffer.split("\n\n");
        buffer = frames.pop() || "";

        for (const frameText of frames) {
          if (!frameText.trim()) continue;

          const frame = parseSseFrame(frameText);
          if (!frame) continue;

          try {
            if (frame.event === "state_snapshot") {
              const state: ResearchRunState = JSON.parse(frame.data);
              if (state.timeline) {
                setEvents(state.timeline);
              }
            } else if (frame.event === "timeline_event") {
              const event: TimelineEvent = JSON.parse(frame.data);
              setEvents(prev => {
                if (prev.some(e => e.id === event.id)) return prev;
                return [...prev, event];
              });
            }
          } catch {
          }
        }
      }

      setIsConnected(false);
    } catch (err) {
      if (err instanceof Error && err.name === "AbortError") {
        return;
      }
      setError(err instanceof Error ? err.message : "Connection failed");
      setIsConnected(false);
      setIsLoading(false);
    }
  }, [runId]);

  useEffect(() => {
    connectToStream();

    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, [connectToStream]);

  if (isLoading) {
    return (
      <div className="rounded-xl border border-slate-800 bg-slate-900/50 w-full p-6">
        <h3 className="text-lg font-semibold text-white mb-4">Research Activity</h3>
        <div className="flex items-center justify-center py-8 text-slate-400">
          <Loader2 className="h-5 w-5 animate-spin mr-2" />
          <span>Connecting to activity stream...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-xl border border-slate-800 bg-slate-900/50 w-full p-6">
        <h3 className="text-lg font-semibold text-white mb-4">Research Activity</h3>
        <div className="flex flex-col items-center justify-center py-8 text-slate-400">
          <AlertCircle className="h-8 w-8 text-red-400 mb-2" />
          <p className="text-sm text-red-400">{error}</p>
          <button
            onClick={connectToStream}
            className="mt-3 text-xs text-emerald-400 hover:text-emerald-300 underline"
          >
            Try again
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/50 w-full p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-white">Research Activity</h3>
        <div className="flex items-center gap-2">
          <div
            className={cn(
              "w-2 h-2 rounded-full",
              isConnected ? "bg-emerald-500 animate-pulse" : "bg-slate-500"
            )}
          />
          <span className="text-xs text-slate-400">
            {isConnected ? "Live" : "Disconnected"}
          </span>
        </div>
      </div>

      {stageGroups.length === 0 ? (
        <div className="text-center py-8 text-slate-400">
          <p className="text-sm">No activity yet</p>
          <p className="text-xs mt-1">Events will appear as the research progresses.</p>
        </div>
      ) : (
        <ScrollArea ref={scrollAreaRef} style={{ height: maxHeight }}>
          <div className="space-y-3 pr-4">
            {stageGroups.map(stage => (
              <StageSection
                key={stage.stageId}
                stage={stage}
                isExpanded={expandedStages.has(stage.stageId)}
                onToggle={() => toggleStage(stage.stageId)}
              />
            ))}
          </div>
        </ScrollArea>
      )}
    </div>
  );
}
