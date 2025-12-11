"use client";

import type { SubstageEvent, StageProgress, PaperGenerationEvent } from "@/types/research";
import { Tooltip, TooltipTrigger, TooltipContent } from "@/shared/components/ui/tooltip";

interface ResearchPipelineStagesProps {
  stageProgress: StageProgress[];
  substageEvents: SubstageEvent[];
  paperGenerationProgress: PaperGenerationEvent[];
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

/**
 * Helper function to extract stage slug from backend stage name
 *
 * Backend format: {stage_number}_{stage_slug}_{substage_number}_{substage_name}
 * Examples:
 *   "1_initial_implementation_1_preliminary" → "initial_implementation"
 *   "2_baseline_tuning_2_optimization" → "baseline_tuning"
 *   "3_creative_research_1_exploration" → "creative_research"
 */
const extractStageSlug = (stageName: string): string | null => {
  const parts = stageName.split("_");

  // Need at least 4 parts: stage_number + slug + substage_number + substage_name
  if (parts.length < 4) return null;

  // Skip first part (stage number), collect parts until we hit next number (substage number)
  const slugParts: string[] = [];
  for (let i = 1; i < parts.length; i++) {
    const part = parts[i];
    if (!part) continue;
    // Stop when we hit a number (substage number)
    if (/^\d+$/.test(part)) break;
    slugParts.push(part);
  }

  return slugParts.length > 0 ? slugParts.join("_") : null;
};

interface StageInfo {
  status: "pending" | "in_progress" | "completed";
  progressPercent: number;
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

// Paper generation step labels for Stage 5
const PAPER_GENERATION_STEPS = [
  { key: "plot_aggregation", label: "Plot Aggregation" },
  { key: "citation_gathering", label: "Citation Gathering" },
  { key: "paper_writeup", label: "Paper Writeup" },
  { key: "paper_review", label: "Paper Review" },
] as const;

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
  paperGenerationProgress,
}: ResearchPipelineStagesProps) {
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
          progressPercent: 0,
          details: null,
        };
      }

      const latestEvent = paperGenerationProgress[paperGenerationProgress.length - 1];
      if (!latestEvent) {
        return {
          status: "pending",
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
        progressPercent: 0,
        details: null,
      };
    }

    // Use the most recent progress event (array is ordered by created_at)
    const latestProgress = stageProgresses[stageProgresses.length - 1];
    if (!latestProgress) {
      return {
        status: "pending",
        progressPercent: 0,
        details: null,
      };
    }
    const progressPercent = Math.round(latestProgress.progress * 100);

    // Determine status based on progress value
    let status: "pending" | "in_progress" | "completed";
    if (latestProgress.progress >= 1.0) {
      status = "completed";
    } else if (latestProgress.progress > 0) {
      status = "in_progress";
    } else {
      status = "pending";
    }

    return {
      status,
      progressPercent,
      details: latestProgress,
    };
  };

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-6 w-full">
      <h2 className="mb-6 text-xl font-semibold text-white">Pipeline Stages</h2>

      <div className="flex flex-col gap-6">
        {PIPELINE_STAGES.map(stage => {
          const info = getStageInfo(stage.key);
          const isPaperGeneration = stage.key === "paper_generation";
          const segments = isPaperGeneration
            ? getPaperGenerationSegments(paperGenerationProgress)
            : getNodeSegments(stage.key, substageEvents, stageProgress);
          const emptyMessage = isPaperGeneration ? "No steps yet" : "No nodes yet";

          return (
            <div key={stage.id} className="flex flex-col gap-3">
              {/* Stage header with title, description, and status */}
              <div className="flex items-start justify-between gap-4">
                <div className="flex flex-col gap-1">
                  <h3 className="text-base font-semibold text-white">
                    Stage {stage.id}: {stage.title}
                    {info.status !== "pending" && (
                      <span className="ml-2 text-slate-400">({info.progressPercent}%)</span>
                    )}
                  </h3>
                </div>
                {/* Status Badge */}
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
              </div>

              {/* Unified progress bar for all stages */}
              <SegmentedProgressBar segments={segments} emptyMessage={emptyMessage} />
            </div>
          );
        })}
      </div>
    </div>
  );
}
