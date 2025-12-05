"use client";

import type { NodeEvent, StageProgress } from "@/types/research";
import { cn } from "@/shared/lib/utils";
import { Tooltip, TooltipTrigger, TooltipContent } from "@/shared/components/ui/tooltip";

interface ResearchPipelineStagesProps {
  stageProgress: StageProgress[];
  experimentNodes: NodeEvent[];
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
 * Enhanced segment data with tooltip information
 */
interface SegmentData {
  status: "good" | "buggy";
  nodeNumber: number;
  nodeId?: string | null;
  isSynthetic: boolean;
}

/**
 * Legend explaining segment colors
 */
function SegmentLegend() {
  return (
    <div className="flex items-center gap-4 text-sm text-slate-400 mb-4">
      <span className="font-medium">Legend:</span>
      <div className="flex items-center gap-2">
        <div className="h-3 w-3 rounded-sm bg-blue-500" />
        <span>Good Node</span>
      </div>
      <div className="flex items-center gap-2">
        <div className="h-3 w-3 rounded-sm bg-red-500" />
        <span>Buggy Node</span>
      </div>
    </div>
  );
}

/**
 * Segmented progress bar showing one segment per node
 */
interface SegmentedProgressBarProps {
  segments: SegmentData[];
}

function SegmentedProgressBar({ segments }: SegmentedProgressBarProps) {
  if (segments.length === 0) {
    return <div className="text-xs text-slate-500">No nodes yet</div>;
  }

  return (
    <div className="flex gap-1 w-full">
      {segments.map((segment, index) => {
        const statusLabel = segment.status === "good" ? "Good" : "Buggy";
        const tooltipText = `Node ${segment.nodeNumber}: ${statusLabel}`;

        return (
          <Tooltip key={index}>
            <TooltipTrigger asChild>
              <div
                className={cn(
                  "h-2 flex-1 rounded-sm transition-all duration-300 cursor-help",
                  segment.status === "good" && "bg-blue-500",
                  segment.status === "buggy" && "bg-red-500"
                )}
              />
            </TooltipTrigger>
            <TooltipContent>
              <p className="text-xs">{tooltipText}</p>
            </TooltipContent>
          </Tooltip>
        );
      })}
    </div>
  );
}

/**
 * Get segments array for a stage (one segment per node, showing good/buggy status)
 * Falls back to synthetic segments from stage progress if no node events exist
 */
const getSegmentsByStage = (
  stageKey: string,
  experimentNodes: NodeEvent[],
  stageProgress: StageProgress[]
): SegmentData[] => {
  // Filter nodes for this stage
  const stageNodes = experimentNodes.filter(node => {
    const slug = extractStageSlug(node.stage);
    return slug === stageKey;
  });

  // If we have actual node events, use them
  if (stageNodes.length > 0) {
    // Sort by creation time (chronological order)
    const sortedNodes = stageNodes.sort(
      (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
    );

    // Map each node to SegmentData with tooltip information
    return sortedNodes.map((node, index) => ({
      status:
        typeof node.summary === "object" && node.summary !== null && "is_buggy" in node.summary
          ? node.summary.is_buggy
            ? "buggy"
            : "good"
          : "good",
      nodeNumber: index + 1,
      nodeId: node.node_id,
      isSynthetic: false,
    }));
  }

  // FALLBACK: If no node events, derive segments from stage progress aggregate data
  // Find the latest progress event for this stage
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

  // Create synthetic segments: show good nodes first, then buggy nodes
  // This is an approximation since we don't know the actual order
  const segments: SegmentData[] = [];
  let nodeNumber = 1;

  // Good nodes first
  for (let i = 0; i < good_nodes; i++) {
    segments.push({
      status: "good",
      nodeNumber: nodeNumber++,
      isSynthetic: true,
    });
  }

  // Buggy nodes second
  for (let i = 0; i < buggy_nodes; i++) {
    segments.push({
      status: "buggy",
      nodeNumber: nodeNumber++,
      isSynthetic: true,
    });
  }

  return segments;
};

/**
 * Pipeline stages section showing all stages with segmented progress bars
 */
export function ResearchPipelineStages({
  stageProgress,
  experimentNodes,
}: ResearchPipelineStagesProps) {
  /**
   * Get aggregated stage information for a given main stage
   * Handles multiple substages within a main stage by using the latest progress
   */
  const getStageInfo = (stageKey: string): StageInfo => {
    // Find all progress events that match this main stage (across all substages)
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

      {/* Legend */}
      <SegmentLegend />

      <div className="flex flex-col gap-6">
        {PIPELINE_STAGES.map(stage => {
          const info = getStageInfo(stage.key);
          const segments = getSegmentsByStage(stage.key, experimentNodes, stageProgress);

          return (
            <div key={stage.id} className="flex flex-col gap-3">
              {/* Stage header with title, description, and status */}
              <div className="flex items-start justify-between gap-4">
                <div className="flex flex-col gap-1">
                  <h3 className="text-base font-semibold text-white">
                    Stage {stage.id}: {stage.title}
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

              {/* Segmented progress bar - one segment per node */}
              <SegmentedProgressBar segments={segments} />
            </div>
          );
        })}
      </div>
    </div>
  );
}
