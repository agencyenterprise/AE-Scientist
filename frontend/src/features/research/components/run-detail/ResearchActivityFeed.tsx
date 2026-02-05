"use client";

import { useEffect, useRef, useState, useCallback, useMemo } from "react";
import { ScrollArea } from "@/shared/components/ui/scroll-area";
import { Button } from "@/shared/components/ui/button";
import { Modal } from "@/shared/components/Modal";
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
  FlaskConical,
  StopCircle,
} from "lucide-react";
import { CopyToClipboardButton } from "@/shared/components/CopyToClipboardButton";
import type { components } from "@/types/api.gen";

type ResearchRunState = components["schemas"]["ResearchRunState"];
type TimelineEvent = NonNullable<ResearchRunState["timeline"]>[number];

interface ResearchActivityFeedProps {
  runId: string;
  maxHeight?: string;
  /** Handler to terminate an active execution. If not provided, terminate buttons won't appear. */
  onTerminateExecution?: (executionId: string, feedback: string) => Promise<void>;
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
  /** Max iterations for this stage (from progress_update events) */
  maxNodes: number | null;
  /** Current iteration number */
  currentIteration: number | null;
  /** Seed evaluation progress: current seed being evaluated (1-based) */
  currentSeed: number | null;
  /** Total number of seeds to evaluate */
  totalSeeds: number | null;
  /** Whether seed evaluation is in progress */
  seedEvalInProgress: boolean;
  /** Whether this stage has any seed evaluation (from is_seed_node flag) */
  hasSeedEvaluation: boolean;
  /** Aggregation progress: current aggregation (1-based) */
  currentAggregation: number | null;
  /** Total number of aggregations (typically 1) */
  totalAggregations: number | null;
  /** Whether aggregation is in progress */
  aggregationInProgress: boolean;
  /** Whether this stage has aggregation (from is_seed_agg_node flag) */
  hasAggregation: boolean;
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

/**
 * Filter events to show only codex_execution events for node executions.
 * runfile_execution events are sub-executions and shouldn't appear as separate items.
 */
function filterNodeExecutionEvents(events: TimelineEvent[]): TimelineEvent[] {
  return events.filter(event => {
    // Keep all non-execution events
    if (event.type !== "node_execution_started" && event.type !== "node_execution_completed") {
      return true;
    }
    // For execution events, only show codex_execution (the main execution)
    if ("run_type" in event) {
      return event.run_type === "codex_execution";
    }
    return true;
  });
}

/**
 * Find the runfile execution event that matches a codex execution (same execution_id)
 */
function findRunfileExecution(
  events: TimelineEvent[],
  executionId: string,
  eventType: "node_execution_started" | "node_execution_completed"
): TimelineEvent | null {
  return (
    events.find(
      e =>
        e.type === eventType &&
        "execution_id" in e &&
        e.execution_id === executionId &&
        "run_type" in e &&
        e.run_type === "runfile_execution"
    ) ?? null
  );
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
  // Filter out runfile_execution events - they're sub-executions of codex_execution
  const filteredEvents = filterNodeExecutionEvents(events);

  const stageMap = new Map<string, TimelineEvent[]>();
  const stageOrder: string[] = [];

  for (const event of filteredEvents) {
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
    const lastProgress =
      progressEvents.length > 0 ? progressEvents[progressEvents.length - 1] : null;
    let progress = 0;
    if (isCompleted) {
      progress = 100;
    } else if (lastProgress && "iteration" in lastProgress && "max_iterations" in lastProgress) {
      progress = Math.round(
        ((lastProgress.iteration as number) / (lastProgress.max_iterations as number)) * 100
      );
    } else if (hasStarted) {
      progress = 10; // Just started
    }

    const timestamps = stageEvents.map(e => new Date(e.timestamp).getTime());
    const startTime =
      timestamps.length > 0 ? new Date(Math.min(...timestamps)).toISOString() : null;
    const endTime =
      isCompleted && timestamps.length > 0 ? new Date(Math.max(...timestamps)).toISOString() : null;

    // Get max_iterations and current iteration from regular progress_update events (not seed)
    const regularProgressEvents = progressEvents.filter(
      e => !("is_seed_node" in e && e.is_seed_node)
    );
    const lastRegularProgress =
      regularProgressEvents.length > 0
        ? regularProgressEvents[regularProgressEvents.length - 1]
        : null;
    let maxNodes: number | null = null;
    let currentIteration: number | null = null;
    if (
      lastRegularProgress &&
      "max_iterations" in lastRegularProgress &&
      "iteration" in lastRegularProgress
    ) {
      maxNodes = lastRegularProgress.max_iterations as number;
      currentIteration = lastRegularProgress.iteration as number;
    }

    // Get seed evaluation progress from progress_update events with is_seed_node=true
    const seedProgressEvents = progressEvents.filter(
      e => "is_seed_node" in e && e.is_seed_node === true
    );
    let currentSeed: number | null = null;
    let totalSeeds: number | null = null;
    let seedEvalInProgress = false;
    const hasSeedEvaluation = seedProgressEvents.length > 0;

    if (seedProgressEvents.length > 0) {
      const lastSeedProgress = seedProgressEvents[seedProgressEvents.length - 1]!;
      if ("iteration" in lastSeedProgress && "max_iterations" in lastSeedProgress) {
        currentSeed = lastSeedProgress.iteration as number;
        totalSeeds = lastSeedProgress.max_iterations as number;
        // Seed eval is in progress if current < total and stage is not completed
        seedEvalInProgress =
          !isCompleted && currentSeed !== null && totalSeeds !== null && currentSeed < totalSeeds;
      }
    }

    // Get aggregation progress from progress_update events with is_seed_agg_node=true
    const aggProgressEvents = progressEvents.filter(
      e => "is_seed_agg_node" in e && e.is_seed_agg_node === true
    );
    let currentAggregation: number | null = null;
    let totalAggregations: number | null = null;
    let aggregationInProgress = false;
    const hasAggregation = aggProgressEvents.length > 0;

    if (aggProgressEvents.length > 0) {
      const lastAggProgress = aggProgressEvents[aggProgressEvents.length - 1]!;
      if ("iteration" in lastAggProgress && "max_iterations" in lastAggProgress) {
        currentAggregation = lastAggProgress.iteration as number;
        totalAggregations = lastAggProgress.max_iterations as number;
        // Aggregation is in progress if current < total and stage is not completed
        aggregationInProgress =
          !isCompleted &&
          currentAggregation !== null &&
          totalAggregations !== null &&
          currentAggregation < totalAggregations;
      }
    }

    return {
      stageId,
      stageName: getStageName(stageId),
      status: isCompleted ? "completed" : hasStarted ? "in_progress" : "pending",
      events: stageEvents,
      progress,
      startTime,
      endTime,
      maxNodes,
      currentIteration,
      currentSeed,
      totalSeeds,
      seedEvalInProgress,
      hasSeedEvaluation,
      currentAggregation,
      totalAggregations,
      aggregationInProgress,
      hasAggregation,
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
      return "Agent Started";
    case "node_execution_completed":
      return "Agent Complete";
    case "paper_generation_step":
      return "Paper Generation";
    case "run_finished":
      return "Run Finished";
    default:
      return type.replace(/_/g, " ");
  }
}

interface CompactEventItemProps {
  event: TimelineEvent;
  allEvents: TimelineEvent[];
  onTerminateExecution?: (executionId: string, feedback: string) => Promise<void>;
}

function CompactEventItem({ event, allEvents, onTerminateExecution }: CompactEventItemProps) {
  const [isTerminateDialogOpen, setIsTerminateDialogOpen] = useState(false);
  const [feedback, setFeedback] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const icon = getEventIcon(event.type);
  const colorClass = getEventColor(event.type);
  const label = getEventLabel(event.type);

  // Check if this is an active codex execution (started but not completed)
  const isActiveExecution =
    event.type === "node_execution_started" &&
    "run_type" in event &&
    event.run_type === "codex_execution" &&
    "execution_id" in event;

  // Check if this is a seed aggregation execution
  const isSeedAggregation =
    isActiveExecution && "is_seed_agg_node" in event && event.is_seed_agg_node === true;

  // Check if there's a completion event for this execution
  const hasCompleted =
    isActiveExecution &&
    "execution_id" in event &&
    allEvents.some(
      e =>
        e.type === "node_execution_completed" &&
        "execution_id" in e &&
        e.execution_id === event.execution_id
    );

  const canTerminate = isActiveExecution && !hasCompleted && onTerminateExecution;

  // Find the matching runfile execution for display
  const runfileEvent =
    isActiveExecution && "execution_id" in event
      ? findRunfileExecution(allEvents, event.execution_id as string, "node_execution_started")
      : null;

  // Get code preview for execution events
  const codexCodePreview =
    event.type === "node_execution_started" && "code_preview" in event
      ? (event.code_preview as string | null)
      : null;

  const runfileCodePreview =
    runfileEvent && "code_preview" in runfileEvent
      ? (runfileEvent.code_preview as string | null)
      : null;

  const handleTerminate = async () => {
    if (!onTerminateExecution || !("execution_id" in event)) return;
    setIsSubmitting(true);
    setError(null);
    try {
      await onTerminateExecution(event.execution_id as string, feedback.trim());
      setIsTerminateDialogOpen(false);
      setFeedback("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to terminate execution");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <>
      <div className="flex items-start gap-3 py-2 px-3 rounded-md hover:bg-muted/30 transition-colors">
        <div className={cn("mt-0.5 shrink-0", colorClass)}>{icon}</div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <span className={cn("text-sm font-medium", colorClass)}>{label}</span>
              {isSeedAggregation && (
                <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-teal-500/20 text-teal-400">
                  Seed Aggregation
                </span>
              )}
            </div>
            <div className="flex items-center gap-2">
              {canTerminate && (
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-6 px-2 text-xs text-red-400 hover:text-red-300 hover:bg-red-500/10"
                  onClick={() => setIsTerminateDialogOpen(true)}
                >
                  <StopCircle className="h-3 w-3 mr-1" />
                  Terminate
                </Button>
              )}
              <span className="text-xs text-muted-foreground shrink-0">
                {formatTimeAgo(event.timestamp)}
              </span>
            </div>
          </div>
          {event.headline && (
            <p className="text-xs text-muted-foreground mt-0.5 line-clamp-1">{event.headline}</p>
          )}
          <EventDetails event={event} />

          {/* Show Coding Agent Task with task prompt */}
          {isActiveExecution && codexCodePreview && (
            <details
              className={cn(
                "mt-2 rounded-md border",
                isSeedAggregation
                  ? "border-teal-500/30 bg-teal-500/5"
                  : "border-blue-500/30 bg-blue-500/5"
              )}
            >
              <summary
                className={cn(
                  "cursor-pointer px-3 py-2 text-xs font-medium flex items-center gap-2",
                  isSeedAggregation
                    ? "text-teal-300 hover:text-teal-200"
                    : "text-blue-300 hover:text-blue-200"
                )}
              >
                <span
                  className={cn(
                    "inline-block w-2 h-2 rounded-full animate-pulse",
                    isSeedAggregation ? "bg-teal-400" : "bg-blue-400"
                  )}
                />
                <span className="flex-1">
                  {isSeedAggregation ? "Seed Aggregation Task" : "Coding Agent Task"}
                </span>
                <CopyToClipboardButton text={codexCodePreview} label="Copy task prompt" />
              </summary>
              <div
                className={cn(
                  "max-h-96 overflow-y-auto border-t p-3",
                  isSeedAggregation ? "border-teal-500/20" : "border-blue-500/20"
                )}
              >
                <p
                  className={cn(
                    "text-[10px] uppercase tracking-wide mb-2",
                    isSeedAggregation ? "text-teal-400" : "text-blue-400"
                  )}
                >
                  Task prompt:
                </p>
                <pre className="text-xs font-mono text-slate-300 whitespace-pre-wrap">
                  {codexCodePreview}
                </pre>
              </div>
            </details>
          )}

          {/* Show Node Execution (runfile) with generated code */}
          {runfileEvent && (
            <details className="mt-2 rounded-md border border-emerald-500/30 bg-emerald-500/5">
              <summary className="cursor-pointer px-3 py-2 text-xs font-medium text-emerald-300 hover:text-emerald-200 flex items-center gap-2">
                {!hasCompleted && (
                  <span className="inline-block w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                )}
                {hasCompleted && <CheckCircle2 className="h-3 w-3 text-emerald-400" />}
                <span className="flex-1">
                  Node Execution {hasCompleted ? "(completed)" : "(running)"}
                </span>
                {runfileCodePreview && (
                  <CopyToClipboardButton text={runfileCodePreview} label="Copy generated code" />
                )}
              </summary>
              <div className="border-t border-emerald-500/20">
                {"headline" in runfileEvent && (
                  <p className="px-3 py-1 text-xs text-slate-500">{runfileEvent.headline}</p>
                )}
                {runfileCodePreview && (
                  <div className="max-h-96 overflow-y-auto p-3 pt-1">
                    <p className="text-[10px] uppercase tracking-wide text-emerald-400 mb-2">
                      Generated runfile.py:
                    </p>
                    <pre className="text-xs font-mono text-slate-300 whitespace-pre-wrap">
                      {runfileCodePreview}
                    </pre>
                  </div>
                )}
              </div>
            </details>
          )}
        </div>
      </div>

      {/* Terminate confirmation dialog */}
      {canTerminate && (
        <Modal
          isOpen={isTerminateDialogOpen}
          onClose={() => !isSubmitting && setIsTerminateDialogOpen(false)}
          title="Terminate execution"
          maxHeight="max-h-[80vh]"
        >
          <p className="text-sm text-slate-200">
            The current execution will be stopped immediately. Optionally provide feedback for the
            next iteration.
          </p>
          <textarea
            className="mt-3 w-full rounded-md border border-slate-700 bg-slate-900 p-3 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-emerald-500"
            rows={4}
            value={feedback}
            onChange={e => setFeedback(e.target.value)}
            placeholder="Example: Stop this run and focus on fixing data loader crashes…"
          />
          {error && <p className="mt-2 text-sm text-red-400">{error}</p>}
          <div className="mt-4 flex justify-end gap-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setIsTerminateDialogOpen(false)}
              disabled={isSubmitting}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              size="sm"
              onClick={handleTerminate}
              disabled={isSubmitting}
            >
              {isSubmitting ? "Sending..." : "Send & terminate"}
            </Button>
          </div>
        </Modal>
      )}
    </>
  );
}

function EventDetails({ event }: { event: TimelineEvent }) {
  switch (event.type) {
    case "run_started":
      return "gpu_type" in event && event.gpu_type ? (
        <p className="text-xs text-muted-foreground mt-0.5">GPU: {event.gpu_type}</p>
      ) : null;

    case "progress_update":
      // For seed nodes, show "Seed X/Y"; for regular nodes, iteration is already shown in header badge
      if ("is_seed_node" in event && event.is_seed_node && "iteration" in event && "max_iterations" in event) {
        return (
          <p className="text-xs text-muted-foreground mt-0.5">
            Seed {event.iteration}/{event.max_iterations}
          </p>
        );
      }
      // Don't show iteration for regular nodes - it's already displayed in the stage header badge
      return null;

    case "node_result": {
      const hasOutcome = "outcome" in event && event.outcome;
      const hasSummary = "summary" in event && event.summary;
      if (!hasOutcome && !hasSummary) return null;
      return (
        <div className="mt-1 space-y-1">
          {hasOutcome && (
            <span
              className={cn(
                "inline-block px-1.5 py-0.5 rounded text-xs font-medium",
                event.outcome === "success"
                  ? "bg-emerald-500/20 text-emerald-400"
                  : "bg-red-500/20 text-red-400"
              )}
            >
              {(event.outcome as string).toUpperCase()}
            </span>
          )}
          {hasSummary && (
            <p className="text-xs text-muted-foreground leading-relaxed line-clamp-3">
              {event.summary as string}
            </p>
          )}
        </div>
      );
    }

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
  allEvents,
  onTerminateExecution,
}: {
  stage: StageGroup;
  isExpanded: boolean;
  onToggle: () => void;
  allEvents: TimelineEvent[];
  onTerminateExecution?: (executionId: string, feedback: string) => Promise<void>;
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
              {stage.currentIteration !== null && stage.maxNodes !== null && (
                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-blue-500/20 text-blue-400">
                  {stage.currentIteration}/{stage.maxNodes} iterations
                </span>
              )}
              {stage.totalSeeds !== null && stage.totalSeeds > 0 && (
                <span
                  className={cn(
                    "inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium",
                    stage.seedEvalInProgress
                      ? "bg-pink-500/20 text-pink-400"
                      : "bg-pink-500/10 text-pink-300"
                  )}
                >
                  <FlaskConical className="h-3 w-3" />
                  {stage.currentSeed || 0}/{stage.totalSeeds} seeds
                  {stage.seedEvalInProgress && <Loader2 className="h-3 w-3 animate-spin ml-1" />}
                </span>
              )}
              {stage.totalAggregations !== null && stage.totalAggregations > 0 && (
                <span
                  className={cn(
                    "inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium",
                    stage.aggregationInProgress
                      ? "bg-teal-500/20 text-teal-400"
                      : "bg-teal-500/10 text-teal-300"
                  )}
                >
                  <Layers className="h-3 w-3" />
                  {stage.currentAggregation || 0}/{stage.totalAggregations} aggregation
                  {stage.aggregationInProgress && <Loader2 className="h-3 w-3 animate-spin ml-1" />}
                </span>
              )}
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
              <CompactEventItem
                key={event.id || idx}
                event={event}
                allEvents={allEvents}
                onTerminateExecution={onTerminateExecution}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export function ResearchActivityFeed({
  runId,
  maxHeight = "500px",
  onTerminateExecution,
}: ResearchActivityFeedProps) {
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
          } catch {}
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
          <span className="text-xs text-slate-400">{isConnected ? "Live" : "Disconnected"}</span>
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
                allEvents={events}
                onTerminateExecution={onTerminateExecution}
              />
            ))}
          </div>
        </ScrollArea>
      )}
    </div>
  );
}
