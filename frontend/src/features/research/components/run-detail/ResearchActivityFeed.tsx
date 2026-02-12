"use client";

import * as Sentry from "@sentry/nextjs";
import { useEffect, useRef, useState, useCallback, useMemo } from "react";
import { ScrollArea } from "@/shared/components/ui/scroll-area";
import { Button } from "@/shared/components/ui/button";
import { Modal } from "@/shared/components/Modal";
import { Tooltip, TooltipTrigger, TooltipContent } from "@/shared/components/ui/tooltip";
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
  Radio,
  HelpCircle,
  MessageSquareText,
} from "lucide-react";
import { CopyToClipboardButton } from "@/shared/components/CopyToClipboardButton";
import { Markdown } from "@/shared/components/Markdown";
import { PIPELINE_STAGES, SKIPPABLE_STAGES } from "@/shared/lib/stage-utils";
import "highlight.js/styles/github-dark.css";
import type { components } from "@/types/api.gen";
import { humanizeEventHeadline, TOOLTIP_EXPLANATIONS } from "../../utils/research-utils";
import type { StageSkipStateMap } from "@/features/research/hooks/useResearchRunDetails";
import type { StageTransitionEvent } from "@/types/research";
import { EXECUTION_TYPE, RUN_TYPE } from "@/types/research";

type ResearchRunState = components["schemas"]["ResearchRunState"];
type ApiTimelineEvent = NonNullable<ResearchRunState["timeline"]>[number];
// Extended timeline event type to include StageTransitionEvent until OpenAPI schema is updated
type TimelineEvent = ApiTimelineEvent | StageTransitionEvent;
type ExecutionType = components["schemas"]["ExecutionType"];

// Define expected pipeline stages in order - these are the stages we show as placeholders
// until they actually start. Uses centralized PIPELINE_STAGES from stage-utils.
// Note: run_started/run_finished events are displayed separately, not as stage cards.
const EXPECTED_STAGES: readonly { id: string; name: string }[] = PIPELINE_STAGES.map(stage => ({
  id: stage.key,
  name: stage.title,
}));

interface ResearchActivityFeedProps {
  runId: string;
  maxHeight?: string;
  /** Handler to terminate an active execution. If not provided, terminate buttons won't appear. */
  onTerminateExecution?: (executionId: string, feedback: string) => Promise<void>;
  /** Current run status (e.g., "running", "completed", "failed") */
  runStatus?: string;
  /** Current termination status */
  terminationStatus?: components["schemas"]["ResearchRunInfo"]["termination_status"];
  /** Map of stage IDs to their skip window state */
  stageSkipState?: StageSkipStateMap;
  /** Stage currently being skipped (pending confirmation from backend) */
  skipPendingStage?: string | null;
  /** Handler to skip a stage. If not provided, skip buttons won't appear. */
  onSkipStage?: (stageId: string) => Promise<void>;
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
  /** LLM-generated transition summary (shown between stages) */
  transitionSummary: string | null;
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
  // Check for run lifecycle events FIRST - these are displayed separately, not in stage cards
  // (even though they may have a stage field set in the backend)
  if (event.type === "run_started") return "_run_start";
  if (event.type === "run_finished") return "_run_end";

  if ("stage" in event && event.stage) {
    return event.stage as string;
  }
  return "_unknown";
}

/**
 * Filter events to show main executions, hiding sub-executions.
 * - codex_execution events: always show (these are the main agent tasks)
 * - runfile_execution events: only show if execution_type is seed or metrics
 *   (runfile_execution with stage_goal or aggregation are sub-executions of codex
 *   and are shown nested under their parent codex_execution via findRunfileExecution)
 */
function filterNodeExecutionEvents(events: TimelineEvent[]): TimelineEvent[] {
  return events.filter(event => {
    // Keep all non-execution events
    if (event.type !== "node_execution_started" && event.type !== "node_execution_completed") {
      return true;
    }
    // For execution events, check run_type and execution_type
    if ("run_type" in event) {
      // Always show codex_execution events
      if (event.run_type === RUN_TYPE.CODEX_EXECUTION) {
        return true;
      }
      // For runfile_execution, only show metrics types
      // (stage_goal, seed, and aggregation runfile_executions are nested under their codex_execution)
      if (event.run_type === RUN_TYPE.RUNFILE_EXECUTION) {
        const execType = "execution_type" in event ? event.execution_type : null;
        return execType === EXECUTION_TYPE.METRICS;
      }
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
        e.run_type === RUN_TYPE.RUNFILE_EXECUTION
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

  for (const event of filteredEvents) {
    const stageId = getEventStage(event);

    if (!stageMap.has(stageId)) {
      stageMap.set(stageId, []);
    }
    stageMap.get(stageId)!.push(event);
  }

  // Helper to create a StageGroup from events
  const createStageGroup = (stageId: string, stageEvents: TimelineEvent[]): StageGroup => {
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

    // Get max_iterations and current iteration from regular progress_update events (not seed or aggregation)
    const regularProgressEvents = progressEvents.filter(
      e =>
        !("is_seed_node" in e && e.is_seed_node) && !("is_seed_agg_node" in e && e.is_seed_agg_node)
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
        const aggProgress =
          "progress" in lastAggProgress ? (lastAggProgress.progress as number) : 0;
        aggregationInProgress =
          !isCompleted &&
          currentAggregation !== null &&
          totalAggregations !== null &&
          aggProgress < 1.0;
      }
    }

    // Extract transition summary from stage_transition events (shown between stages)
    const transitionEvent = stageEvents.find(e => e.type === "stage_transition") as
      | StageTransitionEvent
      | undefined;
    const transitionSummary = transitionEvent?.transition_summary ?? null;

    // Filter out stage_transition events from the events list (they're shown separately)
    const filteredStageEvents = stageEvents.filter(e => e.type !== "stage_transition");

    return {
      stageId,
      stageName: getStageName(stageId),
      status: isCompleted ? "completed" : hasStarted ? "in_progress" : "pending",
      events: filteredStageEvents,
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
      transitionSummary,
    };
  };

  // Helper to create a placeholder StageGroup for stages that haven't started
  const createPlaceholderStage = (stageId: string, stageName: string): StageGroup => ({
    stageId,
    stageName,
    status: "pending",
    events: [],
    progress: 0,
    startTime: null,
    endTime: null,
    maxNodes: null,
    currentIteration: null,
    currentSeed: null,
    totalSeeds: null,
    seedEvalInProgress: false,
    hasSeedEvaluation: false,
    currentAggregation: null,
    totalAggregations: null,
    aggregationInProgress: false,
    hasAggregation: false,
    transitionSummary: null,
  });

  // Build the stage list in expected order, including placeholders
  const result: StageGroup[] = [];

  // Process stages in expected order
  for (const expectedStage of EXPECTED_STAGES) {
    // Find matching stage from events
    let matchingStageId: string | null = null;
    for (const stageId of stageMap.keys()) {
      if (stageId === expectedStage.id) {
        matchingStageId = stageId;
        break;
      }
    }

    if (matchingStageId) {
      // Stage has events - process normally
      const stageEvents = stageMap.get(matchingStageId) || [];
      result.push(createStageGroup(matchingStageId, stageEvents));
    } else {
      // Stage hasn't started yet - add placeholder
      result.push(createPlaceholderStage(expectedStage.id, expectedStage.name));
    }
  }

  return result;
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
    case "stage_transition":
      return <MessageSquareText className="h-3.5 w-3.5" />;
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
    case "stage_transition":
      return "text-indigo-400";
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

function getEventLabel(type: string, event?: TimelineEvent) {
  switch (type) {
    case "run_started":
      return "Research Started";
    case "stage_started":
      return "Stage Started";
    case "stage_completed":
      return "Stage Completed";
    case "stage_transition":
      return "Stage Summary";
    case "progress_update":
      if (event && "is_seed_node" in event && event.is_seed_node) {
        return "Seed Run Started";
      }
      if (event && "is_seed_agg_node" in event && event.is_seed_agg_node) {
        return "Aggregation Run Started";
      }
      return "Iteration Started";
    case "node_result":
      return "Result Ready";
    case "node_execution_started":
      return "Task Started";
    case "node_execution_completed":
      return "Task Completed";
    case "paper_generation_step":
      return "Writing Paper";
    case "run_finished":
      return "Research Finished";
    default:
      return type.replace(/_/g, " ");
  }
}

/**
 * Get humanized headline for an event
 */
function getHumanizedHeadline(event: TimelineEvent): string | null {
  if (!event.headline) return null;

  const nodeName = "node_name" in event ? (event.node_name as string) : undefined;
  return humanizeEventHeadline(event.type, event.headline, nodeName);
}

/**
 * Get the execution type from an event (reads execution_type field from API)
 */
function getExecutionType(event: TimelineEvent): ExecutionType | null {
  if (
    (event.type === "node_execution_started" || event.type === "node_execution_completed") &&
    "execution_type" in event &&
    typeof event.execution_type === "string"
  ) {
    return event.execution_type as ExecutionType;
  }
  return null;
}

/**
 * Check if an execution event is for metrics parsing
 */
function isMetricsExecution(event: TimelineEvent): boolean {
  return getExecutionType(event) === EXECUTION_TYPE.METRICS;
}

/**
 * Get badge configuration for an execution type
 */
function getExecutionTypeBadge(executionType: ExecutionType): {
  label: string;
  tooltip: string;
  bgClass: string;
  textClass: string;
} | null {
  switch (executionType) {
    case EXECUTION_TYPE.METRICS:
      return {
        label: "Metrics",
        tooltip: "Parsing and extracting metrics from experiment outputs.",
        bgClass: "bg-purple-500/20",
        textClass: "text-purple-400",
      };
    case EXECUTION_TYPE.SEED:
      return {
        label: "Seed",
        tooltip:
          "Running the same experiment with different random seeds to ensure statistical validity.",
        bgClass: "bg-pink-500/20",
        textClass: "text-pink-400",
      };
    case EXECUTION_TYPE.AGGREGATION:
      return {
        label: "Aggregation",
        tooltip:
          "Consolidating results from seed runs—computing means and standard deviations across runs.",
        bgClass: "bg-teal-500/20",
        textClass: "text-teal-400",
      };
    case EXECUTION_TYPE.STAGE_GOAL:
      return {
        label: "Experiment",
        tooltip:
          "An experiment variant being explored in the tree search, with its own script, plan, and metrics.",
        bgClass: "bg-blue-500/20",
        textClass: "text-blue-400",
      };
    default:
      return null;
  }
}

/**
 * Get the base node ID from an execution event (strips "_metrics" suffix if present)
 */
function getBaseNodeId(event: TimelineEvent): string | null {
  if (
    (event.type === "node_execution_started" || event.type === "node_execution_completed") &&
    "execution_id" in event &&
    typeof event.execution_id === "string"
  ) {
    const execId = event.execution_id;
    return execId.endsWith("_metrics") ? execId.slice(0, -8) : execId;
  }
  return null;
}

/**
 * Get the node index from an execution event
 */
function getNodeIndex(event: TimelineEvent): number | null {
  if ("node_index" in event && typeof event.node_index === "number") {
    return event.node_index;
  }
  return null;
}

interface NodeExecutionGroup {
  baseNodeId: string;
  nodeIndex: number | null;
  executionType: ExecutionType | null;
  codeEvents: TimelineEvent[];
  metricsEvents: TimelineEvent[];
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
  const [isTaskDetailsOpen, setIsTaskDetailsOpen] = useState(false);
  const [isRunfileDetailsOpen, setIsRunfileDetailsOpen] = useState(false);

  const icon = getEventIcon(event.type);
  const colorClass = getEventColor(event.type);
  const label = getEventLabel(event.type, event);

  // Check if this is an active codex execution (started but not completed)
  const isActiveExecution =
    event.type === "node_execution_started" &&
    "run_type" in event &&
    event.run_type === RUN_TYPE.CODEX_EXECUTION &&
    "execution_id" in event;

  // Get execution type badge configuration (only show on started events, not completed)
  const executionType = getExecutionType(event);
  const executionBadge =
    executionType && event.type === "node_execution_started"
      ? getExecutionTypeBadge(executionType)
      : null;

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
              {executionBadge && (
                <Tooltip>
                  <TooltipTrigger asChild>
                    <span
                      className={cn(
                        "inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium cursor-help",
                        executionBadge.bgClass,
                        executionBadge.textClass
                      )}
                    >
                      {executionBadge.label}
                    </span>
                  </TooltipTrigger>
                  <TooltipContent side="top">{executionBadge.tooltip}</TooltipContent>
                </Tooltip>
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
            <p className="text-xs text-muted-foreground mt-0.5 line-clamp-1">
              {getHumanizedHeadline(event) || event.headline}
            </p>
          )}
          <EventDetails event={event} />

          {/* Show Coding Agent Task with task prompt */}
          {isActiveExecution && codexCodePreview && (
            <details
              open={isTaskDetailsOpen}
              onToggle={e => setIsTaskDetailsOpen(e.currentTarget.open)}
              className={cn(
                "mt-2 rounded-md border",
                executionType === EXECUTION_TYPE.AGGREGATION
                  ? "border-teal-500/30 bg-teal-500/5"
                  : executionType === EXECUTION_TYPE.SEED
                    ? "border-pink-500/30 bg-pink-500/5"
                    : "border-blue-500/30 bg-blue-500/5"
              )}
            >
              <summary
                className={cn(
                  "cursor-pointer px-3 py-2 text-xs font-medium flex items-center gap-2",
                  executionType === EXECUTION_TYPE.AGGREGATION
                    ? "text-teal-300 hover:text-teal-200"
                    : executionType === EXECUTION_TYPE.SEED
                      ? "text-pink-300 hover:text-pink-200"
                      : "text-blue-300 hover:text-blue-200"
                )}
              >
                <span
                  className={cn(
                    "inline-block w-2 h-2 rounded-full animate-pulse",
                    executionType === EXECUTION_TYPE.AGGREGATION
                      ? "bg-teal-400"
                      : executionType === EXECUTION_TYPE.SEED
                        ? "bg-pink-400"
                        : "bg-blue-400"
                  )}
                />
                <span className="flex-1">
                  {executionType === EXECUTION_TYPE.AGGREGATION
                    ? "Aggregation Task"
                    : executionType === EXECUTION_TYPE.SEED
                      ? "Seed Evaluation Task"
                      : "Coding Agent Task"}
                </span>
                <CopyToClipboardButton text={codexCodePreview} label="Copy task prompt" />
              </summary>
              <div
                className={cn(
                  "max-h-96 overflow-y-auto border-t p-3",
                  executionType === EXECUTION_TYPE.AGGREGATION
                    ? "border-teal-500/20"
                    : executionType === EXECUTION_TYPE.SEED
                      ? "border-pink-500/20"
                      : "border-blue-500/20"
                )}
              >
                <p
                  className={cn(
                    "text-[10px] uppercase tracking-wide mb-2",
                    executionType === EXECUTION_TYPE.AGGREGATION
                      ? "text-teal-400"
                      : executionType === EXECUTION_TYPE.SEED
                        ? "text-pink-400"
                        : "text-blue-400"
                  )}
                >
                  Task prompt:
                </p>
                <div className="[&_pre]:!bg-transparent [&_pre]:!border-0 [&_pre]:!p-0 [&_pre]:!m-0 [&_code]:text-[12px] [&_p]:text-[13px] [&_p]:text-slate-300 [&_li]:text-[13px] [&_li]:text-slate-300">
                  <Markdown className="text-slate-300">{codexCodePreview}</Markdown>
                </div>
              </div>
            </details>
          )}

          {/* Show Generated Code (runfile.py) */}
          {runfileEvent && (
            <details
              open={isRunfileDetailsOpen}
              onToggle={e => setIsRunfileDetailsOpen(e.currentTarget.open)}
              className="mt-2 rounded-md border border-emerald-500/30 bg-emerald-500/5"
            >
              <summary className="cursor-pointer px-3 py-2 text-xs font-medium text-emerald-300 hover:text-emerald-200 flex items-center gap-2">
                {!hasCompleted && (
                  <span className="inline-block w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                )}
                {hasCompleted && <CheckCircle2 className="h-3 w-3 text-emerald-400" />}
                <span className="flex-1">
                  Generated Code {hasCompleted ? "(completed)" : "(running)"}
                </span>
                {runfileCodePreview && (
                  <CopyToClipboardButton text={runfileCodePreview} label="Copy generated code" />
                )}
              </summary>
              <div className="border-t border-emerald-500/20">
                {runfileCodePreview && (
                  <div className="max-h-96 overflow-y-auto p-3 pt-1">
                    <p className="text-[10px] uppercase tracking-wide text-emerald-400 mb-2">
                      Generated runfile.py:
                    </p>
                    <div className="[&_pre]:!bg-transparent [&_pre]:!border-0 [&_pre]:!p-0 [&_pre]:!m-0 [&_code]:text-[12px]">
                      <Markdown className="text-slate-300">
                        {"```python\n" + runfileCodePreview + "\n```"}
                      </Markdown>
                    </div>
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
      return "gpu_type" in event ? (
        <p className="text-xs text-muted-foreground mt-0.5">GPU: {event.gpu_type}</p>
      ) : null;

    case "progress_update":
      // Don't show iteration info here - it's already displayed in the event headline
      // and in the stage header badge
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

    // Note: stage_transition events are filtered out and rendered between stages

    default:
      return null;
  }
}

/**
 * Renders a single node execution group (collapsible by default).
 */
function NodeExecutionGroupItem({
  group,
  allEvents,
  onTerminateExecution,
}: {
  group: NodeExecutionGroup;
  allEvents: TimelineEvent[];
  onTerminateExecution?: (executionId: string, feedback: string) => Promise<void>;
}) {
  const [isOpen, setIsOpen] = useState(false);

  // Determine border color based on execution type
  const borderColor =
    group.executionType === EXECUTION_TYPE.AGGREGATION
      ? "border-l-teal-500/50"
      : group.executionType === EXECUTION_TYPE.SEED
        ? "border-l-pink-500/50"
        : "border-l-blue-500/50";

  // Determine header label based on execution type
  const headerLabel =
    group.executionType === EXECUTION_TYPE.AGGREGATION
      ? "Aggregation"
      : group.executionType === EXECUTION_TYPE.SEED
        ? `Seed ${group.nodeIndex ?? "?"}`
        : `Node ${group.nodeIndex ?? "?"} execution`;

  return (
    <details
      open={isOpen}
      onToggle={e => setIsOpen(e.currentTarget.open)}
      className={cn("border-l-2 ml-2", borderColor)}
    >
      {/* Node header (clickable summary) */}
      <summary className="px-3 py-1.5 bg-muted/20 flex items-center gap-2 cursor-pointer hover:bg-muted/30 transition-colors list-none">
        <ChevronRight
          className={cn(
            "h-3 w-3 text-muted-foreground transition-transform",
            isOpen && "rotate-90"
          )}
        />
        <span className="text-xs font-medium text-muted-foreground">{headerLabel}</span>
      </summary>
      {/* Code generation events */}
      {group.codeEvents.map((event, eventIdx) => (
        <div key={event.id || `code-${eventIdx}`} className="relative">
          <CompactEventItem
            event={event}
            allEvents={allEvents}
            onTerminateExecution={onTerminateExecution}
          />
        </div>
      ))}
      {/* Metrics parsing events */}
      {group.metricsEvents.length > 0 && (
        <div className="border-t border-purple-500/20 bg-purple-500/5">
          <div className="px-3 py-1 flex items-center gap-2">
            <span className="text-[10px] uppercase tracking-wide text-purple-400 font-medium">
              Metrics Parsing
            </span>
          </div>
          {group.metricsEvents.map((event, eventIdx) => (
            <CompactEventItem
              key={event.id || `metrics-${eventIdx}`}
              event={event}
              allEvents={allEvents}
              onTerminateExecution={onTerminateExecution}
            />
          ))}
        </div>
      )}
    </details>
  );
}

/**
 * Groups events by node execution, keeping code generation and metrics parsing events together.
 * Non-execution events are rendered individually.
 */
function GroupedEventsList({
  events,
  allEvents,
  onTerminateExecution,
}: {
  events: TimelineEvent[];
  allEvents: TimelineEvent[];
  onTerminateExecution?: (executionId: string, feedback: string) => Promise<void>;
}) {
  // Group execution events by their base node ID
  const groupedItems: Array<
    { type: "single"; event: TimelineEvent } | { type: "group"; group: NodeExecutionGroup }
  > = [];
  const nodeGroups = new Map<string, NodeExecutionGroup>();
  const processedEventIds = new Set<string>();

  // First pass: identify all execution events and group them
  for (const event of events) {
    const baseNodeId = getBaseNodeId(event);
    if (baseNodeId) {
      const eventExecType = getExecutionType(event);
      if (!nodeGroups.has(baseNodeId)) {
        const nodeIndex = getNodeIndex(event);
        nodeGroups.set(baseNodeId, {
          baseNodeId,
          nodeIndex,
          executionType: eventExecType !== EXECUTION_TYPE.METRICS ? eventExecType : null,
          codeEvents: [],
          metricsEvents: [],
        });
      }
      const group = nodeGroups.get(baseNodeId)!;
      // Update execution type if we find a non-metrics type
      if (eventExecType && eventExecType !== EXECUTION_TYPE.METRICS && !group.executionType) {
        group.executionType = eventExecType;
      }
      if (isMetricsExecution(event)) {
        group.metricsEvents.push(event);
      } else {
        group.codeEvents.push(event);
      }
      if (event.id) {
        processedEventIds.add(event.id);
      }
    }
  }

  // Second pass: build the final list maintaining original order
  const emittedGroups = new Set<string>();
  for (const event of events) {
    const baseNodeId = getBaseNodeId(event);
    if (baseNodeId && nodeGroups.has(baseNodeId)) {
      // Emit the group only once, when we encounter the first event of this group
      if (!emittedGroups.has(baseNodeId)) {
        emittedGroups.add(baseNodeId);
        groupedItems.push({ type: "group", group: nodeGroups.get(baseNodeId)! });
      }
    } else {
      // Non-execution event, render individually
      groupedItems.push({ type: "single", event });
    }
  }

  return (
    <>
      {groupedItems.map((item, idx) => {
        if (item.type === "single") {
          return (
            <CompactEventItem
              key={item.event.id || idx}
              event={item.event}
              allEvents={allEvents}
              onTerminateExecution={onTerminateExecution}
            />
          );
        } else {
          return (
            <NodeExecutionGroupItem
              key={item.group.baseNodeId}
              group={item.group}
              allEvents={allEvents}
              onTerminateExecution={onTerminateExecution}
            />
          );
        }
      })}
    </>
  );
}

/**
 * A 3-phase progress bar showing iterations, seeds, and aggregation progress.
 * Each phase has its own fill and hover tooltip.
 */
function StagePhaseProgressBar({ stage }: { stage: StageGroup }) {
  const isCompleted = stage.status === "completed";

  // Calculate progress for each phase (0 to 1)
  // If stage is completed OR a later phase has started, show 100% (even with early exit)
  const seedsStarted = stage.seedEvalInProgress || (stage.currentSeed && stage.currentSeed > 0);
  const aggregationStarted =
    stage.aggregationInProgress || (stage.currentAggregation && stage.currentAggregation > 0);

  const iterationProgress =
    isCompleted || seedsStarted || aggregationStarted
      ? 1 // Iterations done if stage completed OR seeds/aggregation started (early exit)
      : stage.maxNodes && stage.maxNodes > 0
        ? Math.min((stage.currentIteration || 0) / stage.maxNodes, 1)
        : 0;

  const seedProgress =
    (isCompleted && stage.hasSeedEvaluation) || aggregationStarted
      ? 1 // Seeds done if stage completed with seeds OR aggregation started
      : stage.totalSeeds && stage.totalSeeds > 0
        ? Math.min((stage.currentSeed || 0) / stage.totalSeeds, 1)
        : 0;

  const aggregationProgress =
    isCompleted && stage.hasAggregation
      ? 1 // Stage completed with aggregation = aggregation done
      : stage.totalAggregations && stage.totalAggregations > 0
        ? Math.min((stage.currentAggregation || 0) / stage.totalAggregations, 1)
        : 0;

  // Show all 3 phases for stages that are in progress or completed
  const isActiveOrCompleted = stage.status === "in_progress" || stage.status === "completed";
  const showSeeds = isActiveOrCompleted;
  const showAggregation = isActiveOrCompleted;

  // If no progress data at all, don't show the bar
  if (!stage.maxNodes && stage.status === "pending") {
    return null;
  }

  const phases = [
    {
      id: "iterations",
      label: "Iterations",
      progress: iterationProgress,
      current: stage.currentIteration || 0,
      total: stage.maxNodes || 0,
      color: "bg-blue-500",
      bgColor: "bg-blue-500/20",
      show: stage.maxNodes !== null && stage.maxNodes > 0,
      isActive:
        stage.status === "in_progress" && !stage.seedEvalInProgress && !stage.aggregationInProgress,
    },
    {
      id: "seeds",
      label: "Seeds",
      progress: seedProgress,
      current: stage.currentSeed || 0,
      total: stage.totalSeeds || 0,
      color: "bg-pink-500",
      bgColor: "bg-pink-500/20",
      show: showSeeds,
      isActive: stage.seedEvalInProgress,
    },
    {
      id: "aggregation",
      label: "Aggregation",
      progress: aggregationProgress,
      current: stage.currentAggregation || 0,
      total: stage.totalAggregations || 0,
      color: "bg-teal-500",
      bgColor: "bg-teal-500/20",
      show: showAggregation,
      isActive: stage.aggregationInProgress,
    },
  ].filter(phase => phase.show);

  if (phases.length === 0) {
    return null;
  }

  return (
    <div className="flex items-center gap-1 w-full mt-2">
      {phases.map(phase => (
        <Tooltip key={phase.id}>
          <TooltipTrigger asChild>
            <div
              className={cn(
                "relative h-2 rounded-sm overflow-hidden cursor-help transition-all",
                phase.bgColor,
                // Give iterations more weight, seeds and aggregation smaller
                phase.id === "iterations" ? "flex-[3]" : "flex-1"
              )}
            >
              {/* Fill bar */}
              <div
                className={cn(
                  "absolute inset-y-0 left-0 rounded-sm transition-all duration-500",
                  phase.color,
                  phase.isActive && "animate-pulse"
                )}
                style={{ width: `${phase.progress * 100}%` }}
              />
              {/* Active indicator */}
              {phase.isActive && (
                <div className="absolute inset-0 flex items-center justify-center">
                  <div className={cn("w-1 h-1 rounded-full bg-white animate-ping")} />
                </div>
              )}
            </div>
          </TooltipTrigger>
          <TooltipContent side="top">
            {phase.label}: {phase.current}/{phase.total || "?"}
          </TooltipContent>
        </Tooltip>
      ))}
    </div>
  );
}

/**
 * Banner displayed at the top of Research Activity when research has started.
 * Shows GPU type and start time outside of stage cards.
 */
function ResearchStartedBanner({ event }: { event: TimelineEvent }) {
  const gpuType = "gpu_type" in event ? (event.gpu_type as string) : null;
  const timestamp = event.timestamp;

  return (
    <div className="flex items-center gap-3 px-4 py-3 rounded-lg bg-emerald-500/10 border border-emerald-500/20 mb-3">
      <div className="flex items-center justify-center w-8 h-8 rounded-full bg-emerald-500/20">
        <Play className="h-4 w-4 text-emerald-400" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-emerald-300">Research Started</p>
        <p className="text-xs text-slate-400">
          {gpuType && <span>GPU: {gpuType} · </span>}
          {formatTimeAgo(timestamp)}
        </p>
      </div>
    </div>
  );
}

/**
 * Banner displayed at the bottom of Research Activity when research has finished.
 */
function ResearchFinishedBanner({ event }: { event: TimelineEvent }) {
  const status = "status" in event ? (event.status as string) : null;
  const success = "success" in event ? (event.success as boolean) : false;
  const timestamp = event.timestamp;

  return (
    <div
      className={cn(
        "flex items-center gap-3 px-4 py-3 rounded-lg border mt-3",
        success ? "bg-emerald-500/10 border-emerald-500/20" : "bg-red-500/10 border-red-500/20"
      )}
    >
      <div
        className={cn(
          "flex items-center justify-center w-8 h-8 rounded-full",
          success ? "bg-emerald-500/20" : "bg-red-500/20"
        )}
      >
        <Flag className={cn("h-4 w-4", success ? "text-emerald-400" : "text-red-400")} />
      </div>
      <div className="flex-1 min-w-0">
        <p className={cn("text-sm font-medium", success ? "text-emerald-300" : "text-red-300")}>
          Research {success ? "Completed" : "Finished"}
        </p>
        <p className="text-xs text-slate-400">
          {status && <span className="capitalize">{status} · </span>}
          {formatTimeAgo(timestamp)}
        </p>
      </div>
    </div>
  );
}

function StageSection({
  stage,
  isExpanded,
  onToggle,
  allEvents,
  onTerminateExecution,
  runStatus,
  stageSkipState,
  skipPendingStage,
  onSkipStage,
}: {
  stage: StageGroup;
  isExpanded: boolean;
  onToggle: () => void;
  allEvents: TimelineEvent[];
  onTerminateExecution?: (executionId: string, feedback: string) => Promise<void>;
  runStatus?: string;
  stageSkipState?: StageSkipStateMap;
  skipPendingStage?: string | null;
  onSkipStage?: (stageId: string) => Promise<void>;
}) {
  const [isSkipDialogOpen, setIsSkipDialogOpen] = useState(false);
  const [isSkipSubmitting, setIsSkipSubmitting] = useState(false);
  const [skipError, setSkipError] = useState<string | null>(null);

  // Determine if this stage can be skipped
  const stageId = stage.stageId;

  // Stages 1-4 are skippable, Stage 5 (paper_generation) is NOT skippable
  const isSkippableStage = (SKIPPABLE_STAGES as readonly string[]).includes(stageId);

  // Button is shown for stages 1-3 while in progress, but disabled when:
  // - No skip window is open (no best node found yet)
  // - Run is not running
  // - No skip handler provided
  const hasSkipWindow = stageSkipState && stageId in stageSkipState;
  const isStageCompleted = stage.status === "completed";
  const canShowSkipButton = isSkippableStage && onSkipStage && !isStageCompleted;
  const isSkipEnabled = hasSkipWindow && runStatus === "running";

  const effectiveSkipPending = skipPendingStage === stageId || isSkipSubmitting;

  const handleSkipClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    setIsSkipDialogOpen(true);
    setSkipError(null);
  };

  const handleConfirmSkip = async () => {
    if (!onSkipStage) return;
    setIsSkipSubmitting(true);
    setSkipError(null);
    try {
      await onSkipStage(stageId);
      setIsSkipDialogOpen(false);
    } catch (err) {
      setSkipError(err instanceof Error ? err.message : "Failed to skip stage");
    } finally {
      setIsSkipSubmitting(false);
    }
  };
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
      <div className="w-full flex items-center justify-between gap-2 sm:gap-4 p-3 sm:p-4 hover:bg-muted/30 transition-colors">
        {/* Clickable toggle area */}
        <button
          onClick={onToggle}
          className="flex items-center gap-2 sm:gap-3 min-w-0 flex-1 text-left"
        >
          <ChevronRight
            className={cn(
              "h-4 w-4 text-muted-foreground shrink-0 transition-transform mt-1",
              isExpanded && "rotate-90"
            )}
          />
          <div className="flex-1 min-w-0">
            {/* Stage name and status */}
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-semibold text-foreground">{stage.stageName}</span>
              {statusBadge[stage.status]}
            </div>

            {/* Progress badges - wrap on their own line on mobile */}
            <div className="flex flex-wrap items-center gap-1.5 sm:gap-2 mt-2">
              {stage.currentIteration !== null && stage.maxNodes !== null && (
                <Tooltip>
                  <TooltipTrigger asChild>
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-blue-500/20 text-blue-400 cursor-help">
                      {stage.currentIteration}/{stage.maxNodes} iterations
                    </span>
                  </TooltipTrigger>
                  <TooltipContent
                    side="top"
                    className="max-w-xs bg-slate-800 text-slate-200 border-slate-700"
                  >
                    {TOOLTIP_EXPLANATIONS.iterations}
                  </TooltipContent>
                </Tooltip>
              )}
              {stage.totalSeeds !== null && stage.totalSeeds > 0 && (
                <Tooltip>
                  <TooltipTrigger asChild>
                    <span
                      className={cn(
                        "inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium cursor-help",
                        stage.seedEvalInProgress
                          ? "bg-pink-500/20 text-pink-400"
                          : "bg-pink-500/10 text-pink-300"
                      )}
                    >
                      <FlaskConical className="h-3 w-3" />
                      {stage.currentSeed || 0}/{stage.totalSeeds} seeds
                      {stage.seedEvalInProgress && (
                        <Loader2 className="h-3 w-3 animate-spin ml-1" />
                      )}
                    </span>
                  </TooltipTrigger>
                  <TooltipContent
                    side="top"
                    className="max-w-xs bg-slate-800 text-slate-200 border-slate-700"
                  >
                    {TOOLTIP_EXPLANATIONS.seeds}
                  </TooltipContent>
                </Tooltip>
              )}
              {stage.totalAggregations !== null && stage.totalAggregations > 0 && (
                <Tooltip>
                  <TooltipTrigger asChild>
                    <span
                      className={cn(
                        "inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium cursor-help",
                        stage.aggregationInProgress
                          ? "bg-teal-500/20 text-teal-400"
                          : "bg-teal-500/10 text-teal-300"
                      )}
                    >
                      <Layers className="h-3 w-3" />
                      {stage.currentAggregation || 0}/{stage.totalAggregations} aggregation
                      {stage.aggregationInProgress && (
                        <Loader2 className="h-3 w-3 animate-spin ml-1" />
                      )}
                    </span>
                  </TooltipTrigger>
                  <TooltipContent
                    side="top"
                    className="max-w-xs bg-slate-800 text-slate-200 border-slate-700"
                  >
                    {TOOLTIP_EXPLANATIONS.aggregation}
                  </TooltipContent>
                </Tooltip>
              )}
            </div>

            {/* 3-phase progress bar - only for experiment stages (1-4) */}
            {isSkippableStage && <StagePhaseProgressBar stage={stage} />}

            <p className="text-xs text-muted-foreground mt-1.5">
              {stage.events.length} event{stage.events.length !== 1 ? "s" : ""}
              {duration && ` • ${duration}`}
            </p>
          </div>
        </button>

        {/* Actions area - not nested in button */}
        <div className="flex items-center gap-2 sm:gap-3 shrink-0">
          {canShowSkipButton && (
            <div className="flex items-center gap-1">
              <Button
                variant="outline"
                size="sm"
                onClick={handleSkipClick}
                disabled={!isSkipEnabled || effectiveSkipPending}
                className="h-7 px-2 text-xs"
              >
                {effectiveSkipPending ? "Skipping…" : "Skip Stage"}
              </Button>
              <Tooltip>
                <TooltipTrigger asChild>
                  <button
                    type="button"
                    className="p-1 text-muted-foreground hover:text-foreground transition-colors"
                  >
                    <HelpCircle className="h-3.5 w-3.5" />
                  </button>
                </TooltipTrigger>
                <TooltipContent side="top" className="max-w-64 text-xs">
                  {isSkipEnabled
                    ? "A best node has been found. You can skip remaining goal node iterations and proceed directly to seed evaluation and aggregation."
                    : "Skip becomes available once a best node is found for this stage. Skipping will stop remaining goal node iterations."}
                </TooltipContent>
              </Tooltip>
            </div>
          )}
        </div>
      </div>

      {isExpanded && (
        <div className="border-t border-border bg-muted/10">
          <div className="divide-y divide-border/50">
            <GroupedEventsList
              events={stage.events}
              allEvents={allEvents}
              onTerminateExecution={onTerminateExecution}
            />
          </div>
        </div>
      )}

      {/* Stage transition summary - footer of the card */}
      {stage.transitionSummary && (
        <div className="border-t border-indigo-500/20 bg-gradient-to-r from-indigo-500/5 via-purple-500/5 to-indigo-500/5 px-4 py-3">
          <div className="flex items-start gap-2.5">
            <MessageSquareText className="h-4 w-4 text-indigo-400 mt-0.5 flex-shrink-0" />
            <p className="text-sm text-slate-300 leading-relaxed">{stage.transitionSummary}</p>
          </div>
        </div>
      )}

      {/* Skip Stage Confirmation Modal */}
      {onSkipStage && (
        <Modal
          isOpen={isSkipDialogOpen}
          onClose={() => !effectiveSkipPending && setIsSkipDialogOpen(false)}
          title="Skip current stage?"
          maxWidth="max-w-lg"
        >
          <div className="space-y-4">
            <p className="text-sm text-slate-300">
              Skipping <span className="font-semibold text-white">{stage.stageName}</span> will stop
              remaining &quot;goal&quot; node iterations and proceed directly to seed evaluation and
              aggregation using the current best node.
            </p>
            <div className="rounded-md border border-yellow-500/30 bg-yellow-500/10 p-3">
              <p className="text-sm text-yellow-200">
                <span className="font-semibold">Warning:</span> Skipping early may affect the
                quality of your experiment. Additional iterations could potentially find better
                solutions. This action cannot be undone.
              </p>
            </div>
          </div>
          {skipError && <p className="mt-4 text-sm text-red-400">{skipError}</p>}
          <div className="mt-6 flex justify-end gap-3">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setIsSkipDialogOpen(false)}
              disabled={effectiveSkipPending}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              size="sm"
              onClick={handleConfirmSkip}
              disabled={effectiveSkipPending}
            >
              {effectiveSkipPending ? "Skipping..." : "Skip Stage"}
            </Button>
          </div>
        </Modal>
      )}
    </div>
  );
}

export function ResearchActivityFeed({
  runId,
  maxHeight,
  onTerminateExecution,
  runStatus,
  terminationStatus,
  stageSkipState,
  skipPendingStage,
  onSkipStage,
}: ResearchActivityFeedProps) {
  const [events, setEvents] = useState<TimelineEvent[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedStages, setExpandedStages] = useState<Set<string>>(new Set());
  const abortControllerRef = useRef<AbortController | null>(null);
  const scrollAreaRef = useRef<HTMLDivElement>(null);

  // Check if the run has finished (terminal status or terminated)
  const isRunFinished =
    runStatus === "completed" || runStatus === "failed" || terminationStatus === "terminated";

  // Extract run lifecycle events (displayed separately from stage cards)
  const runStartedEvent = useMemo(
    () => events.find(e => e.type === "run_started") ?? null,
    [events]
  );
  const runFinishedEvent = useMemo(
    () => events.find(e => e.type === "run_finished") ?? null,
    [events]
  );

  const stageGroups = useMemo(() => {
    const groups = groupEventsByStage(events);

    // Filter out run lifecycle pseudo-stages - they're displayed as banners instead
    const filteredGroups = groups.filter(
      g => g.stageId !== "_run_start" && g.stageId !== "_run_end"
    );

    // If the run is finished, we shouldn't show any stages as "in_progress"
    // Mark in_progress stages with events as "completed" (they were interrupted)
    if (isRunFinished) {
      return filteredGroups.map(stage => {
        if (stage.status === "in_progress") {
          return { ...stage, status: "completed" as const };
        }
        return stage;
      });
    }

    return filteredGroups;
  }, [events, isRunFinished]);

  useEffect(() => {
    // Auto-expand in-progress stage, auto-collapse completed stages
    const inProgressStage = stageGroups.find(s => s.status === "in_progress");
    const completedStageIds = stageGroups.filter(s => s.status === "completed").map(s => s.stageId);

    setExpandedStages(prev => {
      const next = new Set(prev);
      // Collapse completed stages
      for (const id of completedStageIds) {
        next.delete(id);
      }
      // Expand in-progress stage
      if (inProgressStage) {
        next.add(inProgressStage.stageId);
      }
      return next;
    });
  }, [stageGroups]);

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
        credentials: "include", // Required for Firefox CORS with streaming
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
          } catch (parseError) {
            Sentry.captureException(parseError, {
              extra: { frame, runId },
              tags: { component: "ResearchActivityFeed" },
            });
          }
        }
      }

      setIsConnected(false);
    } catch (err) {
      if (err instanceof Error && err.name === "AbortError") {
        return;
      }
      // Auto-reload the page on stream errors, with rate limiting to prevent infinite loops
      const RELOAD_KEY = `activity-feed-reload-${runId}`;
      const RELOAD_WINDOW_MS = 30000; // 30 seconds
      const MAX_RELOADS = 3;

      const now = Date.now();
      const reloadHistory: number[] = JSON.parse(sessionStorage.getItem(RELOAD_KEY) || "[]");
      // Filter to only recent reloads
      const recentReloads = reloadHistory.filter(t => now - t < RELOAD_WINDOW_MS);

      if (recentReloads.length < MAX_RELOADS) {
        // Record this reload and trigger it
        recentReloads.push(now);
        sessionStorage.setItem(RELOAD_KEY, JSON.stringify(recentReloads));
        window.location.reload();
      } else {
        // Too many reloads, fall back to showing error state
        setError(err instanceof Error ? err.message : "Connection failed");
        setIsConnected(false);
        setIsLoading(false);
      }
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
      <div className="rounded-xl border border-slate-800 bg-slate-900/50 w-full p-4 sm:rounded-2xl sm:p-6">
        <h3 className="text-base font-semibold text-white mb-4 sm:text-lg">Research Activity</h3>
        <div className="flex items-center justify-center py-8 text-slate-400">
          <Loader2 className="h-5 w-5 animate-spin mr-2" />
          <span>Connecting to activity stream...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-xl border border-slate-800 bg-slate-900/50 w-full p-4 sm:rounded-2xl sm:p-6">
        <h3 className="text-base font-semibold text-white mb-4 sm:text-lg">Research Activity</h3>
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
    <div className="rounded-xl border border-slate-800 bg-slate-900/50 w-full p-4 sm:rounded-2xl sm:p-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between mb-4">
        <h3 className="text-base font-semibold text-white sm:text-lg">Research Activity</h3>
        {isConnected && !isRunFinished ? (
          <div className="flex items-center gap-2 rounded-full bg-emerald-500/15 px-3 py-1.5 sm:px-4 sm:py-2 self-start sm:self-auto">
            <span className="relative flex h-2.5 w-2.5 sm:h-3 sm:w-3">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
              <span className="relative inline-flex h-2.5 w-2.5 sm:h-3 sm:w-3 rounded-full bg-emerald-500" />
            </span>
            <Radio className="h-3.5 w-3.5 sm:h-4 sm:w-4 text-emerald-400" />
            <span className="text-xs sm:text-sm font-medium text-emerald-300">Watching Live</span>
          </div>
        ) : (
          <div className="flex items-center gap-2 rounded-full bg-slate-700/50 px-3 py-1.5 sm:px-4 sm:py-2 self-start sm:self-auto">
            <div className="w-2 h-2 sm:w-2.5 sm:h-2.5 rounded-full bg-slate-500" />
            <span className="text-xs sm:text-sm text-slate-400">Disconnected</span>
          </div>
        )}
      </div>

      {stageGroups.length === 0 && !runStartedEvent ? (
        <div className="text-center py-8 text-slate-400">
          <p className="text-sm">No activity yet</p>
          <p className="text-xs mt-1">Events will appear as the research progresses.</p>
        </div>
      ) : (
        <ScrollArea ref={scrollAreaRef} style={maxHeight ? { height: maxHeight } : undefined}>
          {/* Research Started banner - shown above stage cards */}
          {runStartedEvent && <ResearchStartedBanner event={runStartedEvent} />}

          {/* Stage cards */}
          <div className="space-y-3">
            {stageGroups.map(stage => (
              <StageSection
                key={stage.stageId}
                stage={stage}
                isExpanded={expandedStages.has(stage.stageId)}
                onToggle={() => toggleStage(stage.stageId)}
                allEvents={events}
                onTerminateExecution={onTerminateExecution}
                runStatus={runStatus}
                stageSkipState={stageSkipState}
                skipPendingStage={skipPendingStage}
                onSkipStage={onSkipStage}
              />
            ))}
          </div>

          {/* Research Finished banner - shown below stage cards */}
          {runFinishedEvent && <ResearchFinishedBanner event={runFinishedEvent} />}
        </ScrollArea>
      )}
    </div>
  );
}
