"use client";

import { useEffect, useMemo, useState } from "react";
import type {
  StageEvent,
  StageProgress,
  PaperGenerationEvent,
  StageSummary,
  ResearchRunCodeExecution,
} from "@/types/research";
import { cn } from "@/shared/lib/utils";
import { extractStageNumber, PIPELINE_STAGES, STAGE_ID } from "@/shared/lib/stage-utils";
import { Modal } from "@/shared/components/Modal";
import { Button } from "@/shared/components/ui/button";
import { ApiError } from "@/shared/lib/api-client";
import type { StageSkipStateMap } from "@/features/research/hooks/useResearchRunDetails";
import { CopyToClipboardButton } from "@/shared/components/CopyToClipboardButton";

interface ResearchPipelineStagesProps {
  stageProgress: StageProgress[];
  stageEvents: StageEvent[];
  stageSummaries: StageSummary[];
  paperGenerationProgress: PaperGenerationEvent[];
  stageSkipState: StageSkipStateMap;
  codexExecution?: ResearchRunCodeExecution | null;
  runfileExecution?: ResearchRunCodeExecution | null;
  runStatus: string;
  onTerminateExecution?: (executionId: string, feedback: string) => Promise<void>;
  onSkipStage?: (stageId: string) => Promise<void>;
  skipPendingStage?: string | null;
  className?: string;
}

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

const formatNodeId = (nodeId: string): string => {
  if (nodeId.length <= 12) return nodeId;
  return `${nodeId.slice(0, 6)}…${nodeId.slice(-4)}`;
};

const getLatestSummaryForStage = (
  stageKey: string,
  summaries: StageSummary[]
): StageSummary | null => {
  const matches = summaries.filter(summary => summary.stage === stageKey);
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

export function ResearchPipelineStages({
  stageProgress,
  stageEvents,
  stageSummaries,
  paperGenerationProgress,
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
   * Handles multiple iterations within a main stage by using the latest progress
   */
  const getStageInfo = (stageKey: string): StageInfo => {
    // Stage 5 (paper_generation) uses paperGenerationProgress instead of stageProgress
    if (stageKey === STAGE_ID.PAPER_GENERATION) {
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
    const stageProgresses = stageProgress.filter(progress => progress.stage === stageKey);

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
    const hasCompletedEvent = stageEvents.some(event => event.stage === stageKey);

    // Check if this is the currently active stage by looking at the GLOBAL latest progress
    const globalLatestProgress = stageProgress[stageProgress.length - 1];
    const isCurrentlyActive = globalLatestProgress && globalLatestProgress.stage === stageKey;

    // Check if paper generation has started (which means all stages 1-4 are complete)
    const paperGenerationStarted = paperGenerationProgress.length > 0;

    // Determine status based on progress value OR good_nodes (early completion)
    // A stage is completed when:
    // 1. progress >= 1.0 (exhausted all iterations), OR
    // 2. Has stage_completed event AND is no longer the active stage, OR
    // 3. Paper generation has started (stages 1-4 only)
    let status: "pending" | "in_progress" | "completed";
    if (
      latestProgress.progress >= 1.0 ||
      (hasCompletedEvent && !isCurrentlyActive) ||
      paperGenerationStarted
    ) {
      status = "completed";
    } else if (latestProgress.progress > 0 || latestProgress.iteration > 0) {
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
    <div
      className={cn("rounded-2xl border border-slate-800 bg-slate-900/50 p-6 w-full", className)}
    >
      <h2 className="mb-6 text-xl font-semibold text-white">Pipeline Stages</h2>

      <div className="flex flex-col gap-6">
        {PIPELINE_STAGES.map(stage => {
          const info = getStageInfo(stage.key);
          const isPaperGeneration = stage.key === STAGE_ID.PAPER_GENERATION;
          const latestSummary = isPaperGeneration
            ? null
            : getLatestSummaryForStage(stage.key, stageSummaries);
          const summaryText = latestSummary?.summary ?? null;

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
            stageExecution.stage === stage.key;

          const displayMax = info.maxIterations ?? info.iteration ?? 0;
          const displayIteration =
            info.iteration !== null ? Math.min(info.iteration, displayMax) : null;

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

              {!isPaperGeneration && latestSummary && (
                <div className="mt-2 w-full rounded-lg border border-slate-800/60 bg-slate-900/60 p-3 space-y-3">
                  <div>
                    <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">
                      Stage Summary
                    </p>
                    {summaryText && (
                      <div className="mt-1 max-h-32 overflow-y-auto text-xs leading-relaxed text-slate-200 whitespace-pre-wrap">
                        {summaryText}
                      </div>
                    )}
                  </div>
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
  const [nowMs, setNowMs] = useState(() => Date.now());

  useEffect(() => {
    setIsDialogOpen(false);
    setFeedback("");
    setError(null);
    setIsSubmitting(false);
    setRequestAcknowledged(false);
    setNowMs(Date.now());
  }, [executionId]);

  useEffect(() => {
    const intervalId = window.setInterval(() => {
      setNowMs(Date.now());
    }, 1000);
    return () => window.clearInterval(intervalId);
  }, []);

  const codexStartedAtLabel = useMemo(() => {
    if (!codexExecution?.started_at) {
      return "-";
    }
    return new Date(codexExecution.started_at).toLocaleString();
  }, [codexExecution?.started_at]);

  const runfileStartedAtLabel = useMemo(() => {
    if (!runfileExecution?.started_at) {
      return "-";
    }
    return new Date(runfileExecution.started_at).toLocaleString();
  }, [runfileExecution?.started_at]);

  const codexElapsedSeconds = useMemo(() => {
    return getElapsedSecondsForExecution({ execution: codexExecution, nowMs });
  }, [codexExecution, nowMs]);

  const runfileElapsedSeconds = useMemo(() => {
    return getElapsedSecondsForExecution({ execution: runfileExecution, nowMs });
  }, [runfileExecution, nowMs]);

  const formattedCodexDuration = useMemo(() => {
    if (codexElapsedSeconds === null) {
      return "-";
    }
    return formatDurationClockSeconds(codexElapsedSeconds);
  }, [codexElapsedSeconds]);

  const formattedRunfileDuration = useMemo(() => {
    if (runfileElapsedSeconds === null) {
      return "-";
    }
    return formatDurationClockSeconds(runfileElapsedSeconds);
  }, [runfileElapsedSeconds]);

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
            Coding agent execution in progress
          </p>
          <p className="text-sm font-mono text-white">{formatNodeId(executionId)}</p>
          <p className="text-xs text-slate-400">
            Stage{" "}
            {extractStageNumber(codexExecution?.stage ?? runfileExecution?.stage ?? "") ?? "-"} •
            Started {codexStartedAtLabel}
          </p>
          <p className="text-xs text-emerald-200">
            Running for <span className="font-semibold">{formattedCodexDuration}</span>
          </p>
        </div>
        {codexExecution && codexExecution.code && (
          <details className="rounded-md border border-slate-800 bg-slate-950/70 p-3">
            <summary className="cursor-pointer text-xs font-semibold text-slate-200">
              <div className="flex items-center justify-between gap-2">
                <span>Coding agent task</span>
                <span
                  onClick={event => {
                    event.preventDefault();
                    event.stopPropagation();
                  }}
                >
                  <CopyToClipboardButton text={codexExecution.code} label="Copy task code" />
                </span>
              </div>
            </summary>
            <div className="mt-2 max-h-60 overflow-y-auto">
              <pre className="text-xs font-mono text-slate-100 whitespace-pre-wrap">
                {codexExecution.code}
              </pre>
            </div>
          </details>
        )}

        {runfileExecution && runfileExecution.code && (
          <div className="rounded-md border border-slate-800 bg-slate-950/70 p-3">
            <div className="mb-2 flex items-start justify-between gap-3">
              <div className="flex flex-col">
                <p className="text-xs font-semibold text-slate-200">runfile.py</p>
                <p className="text-[11px] text-slate-400">
                  Sub-execution • {runfileExecution.status.toUpperCase()} • Started{" "}
                  {runfileStartedAtLabel}
                </p>
                <p className="text-[11px] text-slate-300">
                  Execution time <span className="font-semibold">{formattedRunfileDuration}</span>
                </p>
              </div>
              <CopyToClipboardButton text={runfileExecution.code} label="Copy runfile code" />
            </div>
            <div className="max-h-60 overflow-y-auto">
              <pre className="text-xs font-mono text-slate-100 whitespace-pre-wrap">
                {runfileExecution.code}
              </pre>
            </div>
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

function formatDurationClockSeconds(totalSeconds: number): string {
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

function getElapsedSecondsForExecution({
  execution,
  nowMs,
}: {
  execution: ResearchRunCodeExecution | null;
  nowMs: number;
}): number | null {
  if (!execution) {
    return null;
  }
  if (typeof execution.exec_time === "number" && Number.isFinite(execution.exec_time)) {
    return Math.max(0, Math.floor(execution.exec_time));
  }
  if (!execution.started_at) {
    return null;
  }
  const startedMs = new Date(execution.started_at).getTime();
  const endMs = execution.completed_at ? new Date(execution.completed_at).getTime() : nowMs;
  if (Number.isNaN(startedMs) || Number.isNaN(endMs)) {
    return null;
  }
  return Math.max(0, Math.floor((endMs - startedMs) / 1000));
}
