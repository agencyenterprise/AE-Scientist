"use client";

import { useEffect, useMemo, useState } from "react";
import type {
  SubstageEvent,
  StageProgress,
  PaperGenerationEvent,
  BestNodeSelection,
  SubstageSummary,
  ResearchRunCodeExecution,
} from "@/types/research";
import { Tooltip, TooltipTrigger, TooltipContent } from "@/shared/components/ui/tooltip";
import { cn } from "@/shared/lib/utils";
import { extractStageSlug, getSummaryText } from "@/shared/lib/stage-utils";
import { Modal } from "@/shared/components/Modal";
import { Button } from "@/shared/components/ui/button";
import { ApiError } from "@/shared/lib/api-client";
import type { StageSkipStateMap } from "@/features/research/hooks/useResearchRunDetails";

interface ResearchPipelineStagesProps {
  stageProgress: StageProgress[];
  substageEvents: SubstageEvent[];
  substageSummaries: SubstageSummary[];
  paperGenerationProgress: PaperGenerationEvent[];
  bestNodeSelections: BestNodeSelection[];
  stageSkipState: StageSkipStateMap;
  codexExecution?: ResearchRunCodeExecution | null;
  runfileExecution?: ResearchRunCodeExecution | null;
  runStatus: string;
  onTerminateExecution?: (executionId: string, feedback: string) => Promise<void>;
  onSkipStage?: (stageSlug: string) => Promise<void>;
  skipPendingStage?: string | null;
  className?: string;
}

// Define pipeline stages with their metadata
// These match the actual backend stage slugs used in the research pipeline
const PIPELINE_STAGES = [
  {
    id: 1,
    key: "initial_implementation",
    title: "Baseline Implementation",
    description: "Generate working baseline implementation with basic functional correctness",
  },
  {
    id: 2,
    key: "baseline_tuning",
    title: "Baseline Tuning",
    description: "Hyperparameter optimization to improve baseline performance",
  },
  {
    id: 3,
    key: "creative_research",
    title: "Creative Research",
    description: "Novel improvements, plotting, and visualization generation",
  },
  {
    id: 4,
    key: "ablation_studies",
    title: "Ablation Studies",
    description: "Component analysis to validate individual contributions",
  },
  {
    id: 5,
    key: "paper_generation",
    title: "Paper Generation",
    description: "Plot aggregation, citation gathering, paper writeup, and peer review",
  },
] as const;

interface StageInfo {
  status: "pending" | "in_progress" | "completed";
  /** For Stages 1-4: current iteration (1-based) */
  iteration: number | null;
  /** For Stages 1-4: max iterations (budget) */
  maxIterations: number | null;
  /** For Stage 5 only: step-based progress percent */
  progressPercent: number | null;
  details: StageProgress | null;
}

/**
 * Unified segment interface for progress bars
 */
interface Segment {
  label: string;
}

/**
 * Unified segmented progress bar component
 * Used for both node-based progress (Stages 1-4) and step-based progress (Stage 5)
 */
interface SegmentedProgressBarProps {
  segments: Segment[];
  emptyMessage?: string;
}

function SegmentedProgressBar({
  segments,
  emptyMessage = "No progress yet",
}: SegmentedProgressBarProps) {
  if (segments.length === 0) {
    return <div className="text-xs text-slate-500">{emptyMessage}</div>;
  }

  return (
    <div className="flex gap-1 w-full">
      {segments.map((segment, index) => (
        <Tooltip key={index}>
          <TooltipTrigger asChild>
            <div className="h-2 flex-1 rounded-sm transition-all duration-300 cursor-help bg-blue-500" />
          </TooltipTrigger>
          <TooltipContent>
            <p className="text-xs">{segment.label}</p>
          </TooltipContent>
        </Tooltip>
      ))}
    </div>
  );
}

/**
 * Get segments array for a stage (one segment per node)
 * Falls back to synthetic segments from stage progress if no node events exist
 */
const getNodeSegments = (
  stageKey: string,
  substageEvents: SubstageEvent[],
  stageProgress: StageProgress[]
): Segment[] => {
  // Filter nodes for this stage
  const stageNodes = substageEvents.filter(node => {
    const slug = extractStageSlug(node.stage);
    return slug === stageKey;
  });

  // If we have actual node events, use them
  if (stageNodes.length > 0) {
    // Sort by creation time (chronological order)
    const sortedNodes = stageNodes.sort(
      (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
    );

    // Map each node to Segment with tooltip label
    return sortedNodes.map((_, index) => ({
      label: `Node ${index + 1}`,
    }));
  }

  // FALLBACK: If no node events, derive segments from stage progress aggregate data
  const stageProgresses = stageProgress.filter(progress => {
    const slug = extractStageSlug(progress.stage);
    return slug === stageKey;
  });

  if (stageProgresses.length === 0) {
    return [];
  }

  // Use the latest progress event
  const latestProgress = stageProgresses[stageProgresses.length - 1];
  if (!latestProgress) return [];
  const { good_nodes, buggy_nodes } = latestProgress;
  const totalNodes = good_nodes + buggy_nodes;

  // Create synthetic segments
  return Array.from({ length: totalNodes }, (_, i) => ({
    label: `Node ${i + 1}`,
  }));
};

const formatNodeId = (nodeId: string): string => {
  if (nodeId.length <= 12) return nodeId;
  return `${nodeId.slice(0, 6)}…${nodeId.slice(-4)}`;
};

const getBestNodeForStage = (
  stageKey: string,
  selections: BestNodeSelection[]
): BestNodeSelection | null => {
  const matches = selections.filter(selection => extractStageSlug(selection.stage) === stageKey);
  if (matches.length === 0) {
    return null;
  }
  return (
    matches.sort(
      (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
    )[0] ?? null
  );
};

const getLatestSummaryForStage = (
  stageKey: string,
  summaries: SubstageSummary[]
): SubstageSummary | null => {
  const matches = summaries.filter(summary => extractStageSlug(summary.stage) === stageKey);
  if (matches.length === 0) {
    return null;
  }
  return (
    matches.sort(
      (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
    )[0] ?? null
  );
};

// Paper generation step labels for Stage 5
const PAPER_GENERATION_STEPS = [
  { key: "plot_aggregation", label: "Plot Aggregation" },
  { key: "citation_gathering", label: "Citation Gathering" },
  { key: "paper_writeup", label: "Paper Writeup" },
  { key: "paper_review", label: "Paper Review" },
] as const;

// Step key to display name mapping for Stage 5 header
const STEP_LABELS: Record<string, string> = {
  plot_aggregation: "Plot Aggregation",
  citation_gathering: "Citation Gathering",
  paper_writeup: "Paper Writeup",
  paper_review: "Paper Review",
};

/**
 * Get segments for paper generation (Stage 5)
 * Shows only completed and current steps
 */
const getPaperGenerationSegments = (events: PaperGenerationEvent[]): Segment[] => {
  if (events.length === 0) {
    return [];
  }

  const latestEvent = events[events.length - 1];
  if (!latestEvent) {
    return [];
  }

  const currentStepIndex = PAPER_GENERATION_STEPS.findIndex(s => s.key === latestEvent.step);

  // Return segments for completed and current steps only
  return PAPER_GENERATION_STEPS.filter((step, index) => {
    const isCompleted = index < currentStepIndex;
    const isCurrent = step.key === latestEvent.step;
    return isCompleted || isCurrent;
  }).map(step => ({
    label: step.label,
  }));
};

export function ResearchPipelineStages({
  stageProgress,
  substageEvents,
  substageSummaries,
  paperGenerationProgress,
  bestNodeSelections,
  stageSkipState,
  codexExecution,
  runfileExecution,
  runStatus,
  onTerminateExecution,
  onSkipStage,
  skipPendingStage,
  className,
}: ResearchPipelineStagesProps) {
  const [skipSubmittingStage, setSkipSubmittingStage] = useState<string | null>(null);
  const [skipErrorStage, setSkipErrorStage] = useState<string | null>(null);
  const [skipErrorMessage, setSkipErrorMessage] = useState<string | null>(null);
  const [skipDialogStage, setSkipDialogStage] = useState<string | null>(null);

  const effectiveSkipStage = skipPendingStage ?? skipSubmittingStage;

  const openSkipDialog = (stageKey: string) => {
    if (!onSkipStage) {
      return;
    }
    setSkipDialogStage(stageKey);
    setSkipErrorStage(null);
    setSkipErrorMessage(null);
  };

  const closeSkipDialog = () => {
    if (effectiveSkipStage && effectiveSkipStage === skipDialogStage) {
      return;
    }
    setSkipDialogStage(null);
  };

  const confirmSkipStage = async () => {
    if (!onSkipStage || !skipDialogStage) {
      return;
    }
    const stageKey = skipDialogStage;
    setSkipSubmittingStage(stageKey);
    setSkipErrorStage(null);
    setSkipErrorMessage(null);
    try {
      await onSkipStage(stageKey);
      setSkipDialogStage(null);
      setSkipSubmittingStage(null);
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Failed to request stage skip. Please try again.";
      setSkipErrorStage(stageKey);
      setSkipErrorMessage(message);
      setSkipSubmittingStage(null);
      return;
    }
  };
  /**
   * Get aggregated stage information for a given main stage
   * Handles multiple substages within a main stage by using the latest progress
   */
  const getStageInfo = (stageKey: string): StageInfo => {
    // Stage 5 (paper_generation) uses paperGenerationProgress instead of stageProgress
    if (stageKey === "paper_generation") {
      if (paperGenerationProgress.length === 0) {
        return {
          status: "pending",
          iteration: null,
          maxIterations: null,
          progressPercent: 0,
          details: null,
        };
      }

      const latestEvent = paperGenerationProgress[paperGenerationProgress.length - 1];
      if (!latestEvent) {
        return {
          status: "pending",
          iteration: null,
          maxIterations: null,
          progressPercent: 0,
          details: null,
        };
      }
      const progressPercent = Math.round(latestEvent.progress * 100);

      let status: "pending" | "in_progress" | "completed";
      if (latestEvent.progress >= 1.0) {
        status = "completed";
      } else {
        status = "in_progress";
      }

      return {
        status,
        iteration: null,
        maxIterations: null,
        progressPercent,
        details: null, // Paper generation doesn't use StageProgress type
      };
    }

    // Stages 1-4 use stageProgress
    const stageProgresses = stageProgress.filter(progress => {
      const slug = extractStageSlug(progress.stage);
      return slug === stageKey;
    });

    // No progress data yet for this stage
    if (stageProgresses.length === 0) {
      return {
        status: "pending",
        iteration: null,
        maxIterations: null,
        progressPercent: 0,
        details: null,
      };
    }

    // Use the most recent progress event (array is ordered by created_at)
    const latestProgress = stageProgresses[stageProgresses.length - 1];
    if (!latestProgress) {
      return {
        status: "pending",
        iteration: null,
        maxIterations: null,
        progressPercent: 0,
        details: null,
      };
    }

    const progressPercent = Math.round(latestProgress.progress * 100);
    const hasCompletedEvent = substageEvents.some(event => {
      const slug = extractStageSlug(event.stage);
      return slug === stageKey;
    });

    // Check if this is the currently active stage by looking at the GLOBAL latest progress
    const globalLatestProgress = stageProgress[stageProgress.length - 1];
    const isCurrentlyActive =
      globalLatestProgress && extractStageSlug(globalLatestProgress.stage) === stageKey;

    // Check if paper generation has started (which means all stages 1-4 are complete)
    const paperGenerationStarted = paperGenerationProgress.length > 0;

    // Determine status based on progress value OR good_nodes (early completion)
    // A stage is completed when:
    // 1. progress >= 1.0 (exhausted all iterations), OR
    // 2. Has substage_completed event AND is no longer the active stage, OR
    // 3. Paper generation has started (stages 1-4 only)
    let status: "pending" | "in_progress" | "completed";
    if (
      latestProgress.progress >= 1.0 ||
      (hasCompletedEvent && !isCurrentlyActive) ||
      paperGenerationStarted
    ) {
      status = "completed";
    } else if (latestProgress.progress > 0) {
      status = "in_progress";
    } else {
      status = "pending";
    }

    return {
      status,
      iteration: latestProgress.iteration,
      maxIterations: latestProgress.max_iterations,
      progressPercent,
      details: latestProgress,
    };
  };

  return (
    <div className={cn("rounded-xl border border-slate-800 bg-slate-900/50 p-6 w-full", className)}>
      <h2 className="mb-6 text-xl font-semibold text-white">Pipeline Stages</h2>

      <div className="flex flex-col gap-6">
        {PIPELINE_STAGES.map(stage => {
          const info = getStageInfo(stage.key);
          const isPaperGeneration = stage.key === "paper_generation";
          const segments = isPaperGeneration
            ? getPaperGenerationSegments(paperGenerationProgress)
            : getNodeSegments(stage.key, substageEvents, stageProgress);
          const emptyMessage = isPaperGeneration ? "No steps yet" : "No nodes yet";
          const bestNode = isPaperGeneration
            ? null
            : getBestNodeForStage(stage.key, bestNodeSelections);
          const latestSummary = isPaperGeneration
            ? null
            : getLatestSummaryForStage(stage.key, substageSummaries);
          const summaryText = latestSummary ? getSummaryText(latestSummary) : null;

          const latestPaperEvent =
            isPaperGeneration && paperGenerationProgress.length > 0
              ? paperGenerationProgress[paperGenerationProgress.length - 1]
              : null;

          const currentStepIndex = latestPaperEvent?.step
            ? PAPER_GENERATION_STEPS.findIndex(s => s.key === latestPaperEvent.step)
            : -1;

          const stageExecution = codexExecution ?? runfileExecution ?? null;
          const isStageExecutionActive =
            runStatus === "running" &&
            stageExecution &&
            stageExecution.status === "running" &&
            extractStageSlug(stageExecution.stage_name) === stage.key;

          const displayMax =
            info.maxIterations ?? (info.iteration !== null ? info.iteration + 1 : 0);
          const displayIteration =
            info.iteration !== null ? Math.min(info.iteration + 1, displayMax) : null;

          const canShowSkipButton = Boolean(
            stageSkipState[stage.key] &&
              runStatus === "running" &&
              typeof onSkipStage === "function" &&
              !isPaperGeneration
          );

          return (
            <div key={stage.id} className="flex flex-col gap-3">
              {/* Stage header with title, description, status, and skip action */}
              <div className="flex flex-col gap-2">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex flex-col gap-1">
                    <h3 className="text-base font-semibold text-white">
                      Stage {stage.id}: {stage.title}
                      {/* Stages 1-4: Show iteration count for in_progress */}
                      {info.status === "in_progress" &&
                        !isPaperGeneration &&
                        info.iteration !== null && (
                          <span className="ml-2 text-slate-400">
                            — Iteration {displayIteration} of {displayMax}
                          </span>
                        )}
                      {/* Stages 1-4: Show completion iteration count for completed */}
                      {info.status === "completed" &&
                        !isPaperGeneration &&
                        info.iteration !== null && (
                          <span className="ml-2 text-slate-400">
                            — Completed in {displayIteration} iterations
                          </span>
                        )}
                      {/* Stage 5: Show step name + step count for in_progress */}
                      {isPaperGeneration &&
                        info.status === "in_progress" &&
                        latestPaperEvent?.step && (
                          <span className="ml-2 text-slate-400">
                            — {STEP_LABELS[latestPaperEvent.step]} (Step {currentStepIndex + 1} of{" "}
                            {PAPER_GENERATION_STEPS.length})
                          </span>
                        )}
                      {/* Stage 5: Show completed message */}
                      {isPaperGeneration && info.status === "completed" && (
                        <span className="ml-2 text-slate-400">
                          — Completed in {PAPER_GENERATION_STEPS.length} steps
                        </span>
                      )}
                    </h3>
                  </div>
                  <div className="flex items-center gap-2">
                    {info.status === "completed" && (
                      <span className="text-sm font-medium uppercase tracking-wide text-slate-400 whitespace-nowrap">
                        COMPLETED
                      </span>
                    )}
                    {info.status === "in_progress" && (
                      <span className="text-sm font-medium uppercase tracking-wide text-blue-400 whitespace-nowrap">
                        IN PROGRESS
                      </span>
                    )}
                    {canShowSkipButton && (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => openSkipDialog(stage.key)}
                        disabled={effectiveSkipStage === stage.key}
                      >
                        {effectiveSkipStage === stage.key ? "Skipping…" : "Skip Stage"}
                      </Button>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {info.status === "completed" && (
                    <span className="text-xs font-medium uppercase tracking-wide text-slate-400 whitespace-nowrap">
                      COMPLETED
                    </span>
                  )}
                  {info.status === "in_progress" && (
                    <span className="text-xs font-medium uppercase tracking-wide text-blue-400 whitespace-nowrap">
                      IN PROGRESS
                    </span>
                  )}
                </div>
                {skipErrorStage === stage.key && skipErrorMessage && (
                  <p className="text-xs text-red-300">{skipErrorMessage}</p>
                )}
              </div>

              {isStageExecutionActive && stageExecution && (
                <ActiveExecutionCard
                  executionId={stageExecution.execution_id}
                  codexExecution={codexExecution ?? null}
                  runfileExecution={runfileExecution ?? null}
                  onTerminateExecution={onTerminateExecution}
                />
              )}

              {/* Unified progress bar for all stages */}
              <SegmentedProgressBar segments={segments} emptyMessage={emptyMessage} />

              {!isPaperGeneration && (bestNode || latestSummary) && (
                <div className="mt-2 w-full rounded-lg border border-slate-800/60 bg-slate-900/60 p-3 space-y-3">
                  {bestNode && (
                    <div>
                      <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">
                        Current Best Node
                      </p>
                      <div className="mt-1 space-y-1">
                        <p className="text-sm font-mono text-emerald-300">
                          {formatNodeId(bestNode.node_id)}
                        </p>
                        <div className="max-h-24 overflow-y-auto text-xs leading-relaxed text-slate-200 whitespace-pre-wrap">
                          {bestNode.reasoning}
                        </div>
                      </div>
                    </div>
                  )}
                  {latestSummary && (
                    <div>
                      <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">
                        Substage Summary
                      </p>
                      {summaryText && (
                        <div className="mt-1 max-h-32 overflow-y-auto text-xs leading-relaxed text-slate-200 whitespace-pre-wrap">
                          {summaryText}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
      <Modal
        isOpen={Boolean(skipDialogStage && onSkipStage)}
        onClose={closeSkipDialog}
        title="Skip current stage?"
        maxWidth="max-w-lg"
      >
        <p className="text-sm text-slate-300">
          Skipping{" "}
          <span className="font-semibold text-white">
            {PIPELINE_STAGES.find(stage => stage.key === skipDialogStage)?.title ??
              skipDialogStage ??
              "this stage"}
          </span>{" "}
          will stop remaining iterations and immediately advance the pipeline to the next stage.
          This action cannot be undone.
        </p>
        {skipErrorStage === skipDialogStage && skipErrorMessage && (
          <p className="mt-4 text-sm text-red-400">{skipErrorMessage}</p>
        )}
        <div className="mt-6 flex justify-end gap-3">
          <Button
            variant="ghost"
            size="sm"
            onClick={closeSkipDialog}
            disabled={effectiveSkipStage !== null && effectiveSkipStage === skipDialogStage}
          >
            Cancel
          </Button>
          <Button
            variant="destructive"
            size="sm"
            onClick={confirmSkipStage}
            disabled={
              !skipDialogStage ||
              (effectiveSkipStage !== null && effectiveSkipStage === skipDialogStage)
            }
          >
            {effectiveSkipStage !== null && effectiveSkipStage === skipDialogStage
              ? "Skipping..."
              : "Skip Stage"}
          </Button>
        </div>
      </Modal>
    </div>
  );
}

interface ActiveExecutionCardProps {
  executionId: string;
  codexExecution: ResearchRunCodeExecution | null;
  runfileExecution: ResearchRunCodeExecution | null;
  onTerminateExecution?: (executionId: string, feedback: string) => Promise<void>;
}

function ActiveExecutionCard({
  executionId,
  codexExecution,
  runfileExecution,
  onTerminateExecution,
}: ActiveExecutionCardProps) {
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [feedback, setFeedback] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [requestAcknowledged, setRequestAcknowledged] = useState(false);
  const startedAtMs = useMemo(() => {
    const started = codexExecution?.started_at ?? runfileExecution?.started_at ?? null;
    return started ? new Date(started).getTime() : Date.now();
  }, [codexExecution?.started_at, runfileExecution?.started_at]);
  const [elapsedSeconds, setElapsedSeconds] = useState(() =>
    Math.max(0, Math.floor((Date.now() - startedAtMs) / 1000))
  );

  useEffect(() => {
    setIsDialogOpen(false);
    setFeedback("");
    setError(null);
    setIsSubmitting(false);
    setRequestAcknowledged(false);
    setElapsedSeconds(Math.max(0, Math.floor((Date.now() - startedAtMs) / 1000)));
  }, [executionId, startedAtMs]);

  useEffect(() => {
    const intervalId = window.setInterval(() => {
      setElapsedSeconds(Math.max(0, Math.floor((Date.now() - startedAtMs) / 1000)));
    }, 1000);
    return () => window.clearInterval(intervalId);
  }, [startedAtMs]);

  const startedAtLabel = new Date(
    codexExecution?.started_at ?? runfileExecution?.started_at ?? Date.now()
  ).toLocaleString();
  const formattedDuration = useMemo(() => formatDuration(elapsedSeconds), [elapsedSeconds]);

  const handleClose = () => {
    if (isSubmitting) {
      return;
    }
    setIsDialogOpen(false);
    setError(null);
  };

  const handleConfirm = async () => {
    if (!onTerminateExecution) {
      return;
    }
    setIsSubmitting(true);
    setError(null);
    try {
      await onTerminateExecution(executionId, feedback.trim());
      setIsDialogOpen(false);
      setFeedback("");
      setRequestAcknowledged(true);
    } catch (err) {
      if (err instanceof ApiError) {
        const data = err.data as { detail?: string } | string | undefined;
        if (typeof data === "string") {
          setError(data);
        } else if (data && typeof data.detail === "string") {
          setError(data.detail);
        } else {
          setError(`Request failed (HTTP ${err.status})`);
        }
      } else if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("Failed to send termination request.");
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <>
      <div className="rounded-lg border border-emerald-500/40 bg-emerald-500/5 p-4 space-y-3">
        <div className="flex flex-col gap-1">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-emerald-300">
            Code execution in progress
          </p>
          <p className="text-sm font-mono text-white">{formatNodeId(executionId)}</p>
          <p className="text-xs text-slate-400">
            Stage {(codexExecution ?? runfileExecution)?.stage_name ?? "-"} • Started{" "}
            {startedAtLabel}
          </p>
          <p className="text-xs text-emerald-200">
            Running for <span className="font-semibold">{formattedDuration}</span>
          </p>
        </div>
        {codexExecution && (
          <details className="rounded-md border border-slate-800 bg-slate-950/70 p-3">
            <summary className="cursor-pointer text-xs font-semibold text-slate-200">
              Codex task (click to expand)
            </summary>
            <div className="mt-2 max-h-60 overflow-y-auto">
              <pre className="text-xs font-mono text-slate-100 whitespace-pre-wrap">
                {codexExecution.code}
              </pre>
            </div>
          </details>
        )}
        {runfileExecution && runfileExecution.status === "running" && (
          <div className="rounded-md border border-slate-800 bg-slate-950/70 p-3 max-h-60 overflow-y-auto">
            <p className="mb-2 text-xs font-semibold text-slate-200">runfile.py (executing)</p>
            <pre className="text-xs font-mono text-slate-100 whitespace-pre-wrap">
              {runfileExecution.code}
            </pre>
          </div>
        )}
        {requestAcknowledged && (
          <p className="text-xs text-amber-300">
            Termination requested. Waiting for the worker to stop…
          </p>
        )}
        {onTerminateExecution && (
          <div className="flex justify-end">
            <Button variant="destructive" size="sm" onClick={() => setIsDialogOpen(true)}>
              Terminate
            </Button>
          </div>
        )}
      </div>

      {onTerminateExecution && (
        <Modal
          isOpen={isDialogOpen}
          onClose={handleClose}
          title="Terminate execution"
          maxHeight="max-h-[80vh]"
        >
          <p className="text-sm text-slate-200">
            The current run will be stopped immediately. Optionally provide feedback for the next
            iteration.
          </p>
          <textarea
            className="mt-3 w-full rounded-md border border-slate-700 bg-slate-900 p-3 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-emerald-500"
            rows={6}
            value={feedback}
            onChange={event => setFeedback(event.target.value)}
            placeholder="Example: Stop this run and focus on fixing data loader crashes…"
          />
          {error && <p className="mt-2 text-sm text-red-400">{error}</p>}
          <div className="mt-4 flex justify-end gap-2">
            <Button variant="ghost" size="sm" onClick={handleClose} disabled={isSubmitting}>
              Cancel
            </Button>
            <Button variant="destructive" size="sm" onClick={handleConfirm} disabled={isSubmitting}>
              {isSubmitting ? "Sending..." : "Send & terminate"}
            </Button>
          </div>
        </Modal>
      )}
    </>
  );
}

function formatDuration(totalSeconds: number): string {
  const clamped = Math.max(0, totalSeconds);
  const hours = Math.floor(clamped / 3600);
  const minutes = Math.floor((clamped % 3600) / 60);
  const seconds = clamped % 60;
  const pad = (value: number) => value.toString().padStart(2, "0");
  if (hours > 0) {
    return `${pad(hours)}:${pad(minutes)}:${pad(seconds)}`;
  }
  return `${pad(minutes)}:${pad(seconds)}`;
}
