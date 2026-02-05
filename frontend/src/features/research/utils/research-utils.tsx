/**
 * Research-specific utility functions
 */
import type { ReactNode } from "react";
import { CheckCircle2, Clock, Loader2, AlertCircle } from "lucide-react";
import { extractStageNumber } from "@/shared/lib/stage-utils";
import { PaperGenerationEvent, StageProgress } from "@/types/research";

/**
 * Stage descriptions for humanizing messages
 */
const STAGE_DESCRIPTIONS: Record<string, { name: string; action: string; description: string }> = {
  "1_baseline": {
    name: "Baseline Implementation",
    action: "Building the foundation",
    description: "Creating the initial working implementation",
  },
  "2_baseline_tuning": {
    name: "Baseline Tuning",
    action: "Optimizing baseline",
    description: "Fine-tuning parameters for better performance",
  },
  "3_creative": {
    name: "Creative Research",
    action: "Exploring creative approaches",
    description: "Testing innovative strategies and novel ideas",
  },
  "4_ablation": {
    name: "Ablation Studies",
    action: "Analyzing component contributions",
    description: "Identifying which components matter most",
  },
  "5_paper": {
    name: "Paper Generation",
    action: "Writing the research paper",
    description: "Generating the final paper with results",
  },
};

/**
 * Maps technical node names to human-readable descriptions
 */
function humanizeNodeName(nodeName: string): string {
  // Extract stage number and type
  const match = nodeName.match(/^(\d+)_([a-z_]+)/i);
  const stageNum = match?.[1];
  const stageType = match?.[2];

  if (!stageNum || !stageType) return nodeName;

  // Map common stage types
  const typeMap: Record<string, string> = {
    baseline: "baseline experiment",
    baseline_tuning: "parameter optimization",
    creative: "creative exploration",
    creati: "creative exploration",
    ablation: "ablation study",
    paper: "paper section",
    paper_generation: "paper writing",
  };

  const humanType = typeMap[stageType] || stageType.replace(/_/g, " ");
  return `${humanType} #${stageNum}`;
}

/**
 * Transforms technical timeline event headlines to human-readable messages
 */
export function humanizeEventHeadline(
  eventType: string,
  headline: string | null | undefined,
  nodeName?: string
): string {
  if (!headline) return "";

  // Handle node execution events
  if (eventType === "node_execution_started" && nodeName) {
    const humanNode = humanizeNodeName(nodeName);
    return `Starting ${humanNode}`;
  }

  if (eventType === "node_execution_completed" && nodeName) {
    const humanNode = humanizeNodeName(nodeName);
    // Extract duration if present
    const durationMatch = headline.match(/\(([\d.]+)s\)/);
    if (durationMatch) {
      return `Completed ${humanNode} in ${durationMatch[1]}s`;
    }
    return `Completed ${humanNode}`;
  }

  // Handle stage events
  if (eventType === "stage_started") {
    const stageMatch = headline.match(/Stage\s+(\d+_[a-z_]+)/i);
    const stageKey = stageMatch?.[1]; // e.g., "2_baseline_tuning"
    if (stageKey) {
      // Direct lookup in STAGE_DESCRIPTIONS using the full key
      const stageInfo = STAGE_DESCRIPTIONS[stageKey];
      if (stageInfo) {
        return stageInfo.action;
      }
    }
    return headline.replace(/Stage\s+\d+_/i, "Starting ");
  }

  if (eventType === "stage_completed") {
    return headline.replace(/Stage\s+\d+_/i, "Completed ");
  }

  // Handle progress updates
  if (eventType === "progress_update") {
    return headline;
  }

  return headline;
}

/**
 * Gets a human-readable description of current research activity
 * Suitable for conference presentations and non-technical audiences
 */
export function getHumanReadableStageDescription(
  stage: string | null,
  status: string,
  progress: number | null
): { title: string; subtitle: string } {
  if (status === "completed") {
    return {
      title: "Research Complete",
      subtitle: "All experiments finished and paper generated",
    };
  }

  if (status === "failed") {
    return {
      title: "Research Stopped",
      subtitle: "An error occurred during the research process",
    };
  }

  if (!stage) {
    if (status === "initializing" || status === "pending") {
      return {
        title: "Preparing Research Environment",
        subtitle: "Setting up GPU and dependencies",
      };
    }
    return {
      title: "Starting Research",
      subtitle: "Initializing the research pipeline",
    };
  }

  // Extract stage number
  const stageNumber = extractStageNumber(stage);
  const progressPercent = progress !== null ? Math.round(progress * 100) : null;

  const stageMessages: Record<string, { title: string; subtitle: string }> = {
    "1": {
      title: "Building Foundation",
      subtitle: "Creating initial implementation and verifying it works",
    },
    "2": {
      title: "Optimizing Performance",
      subtitle: "Fine-tuning parameters to improve results",
    },
    "3": {
      title: "Exploring Creative Ideas",
      subtitle: "Testing innovative approaches and novel strategies",
    },
    "4": {
      title: "Analyzing Results",
      subtitle: "Running ablation studies to understand what works",
    },
    "5": {
      title: "Writing Paper",
      subtitle: "Generating the final research paper with all findings",
    },
  };

  if (stageNumber && stageMessages[stageNumber]) {
    const msg = stageMessages[stageNumber];
    return {
      title: msg.title,
      subtitle:
        progressPercent !== null ? `${msg.subtitle} (${progressPercent}% complete)` : msg.subtitle,
    };
  }

  return {
    title: "Running Research",
    subtitle: stage.replace(/_/g, " "),
  };
}

/**
 * Tooltip explanations for technical terms
 */
export const TOOLTIP_EXPLANATIONS = {
  iterations:
    "Number of experiment cycles run in this stage. Each iteration tests a different approach or variation.",
  seeds:
    "Parallel experiments using different random seeds. Running multiple seeds helps ensure results are reliable and not due to chance.",
  aggregation:
    "Combining results from multiple seed experiments to get a more reliable overall assessment.",
  progress:
    "Overall completion percentage across all research stages (Baseline, Tuning, Creative, Ablation, Paper).",
  evaluation:
    "AI-generated assessment of the research quality based on originality, clarity, significance, and methodology.",
  cost: "Estimated cost based on GPU compute time and API usage for this research run.",
  duration: "Time elapsed since the research started.",
  stage:
    "Current phase of the research pipeline. Research progresses through 5 stages: Baseline, Tuning, Creative, Ablation, and Paper Generation.",
} as const;

export type TooltipKey = keyof typeof TOOLTIP_EXPLANATIONS;

/**
 * Converts backend stage ids into a human-readable label.
 *
 * Backend format: {stage_number}_{stage_slug}[_{substage_number}_{substage_slug}...]
 * Examples:
 * - "5_paper_generation" -> "5: Paper Generation"
 * - "2_baseline_tuning_2_optimization" -> "2: Baseline Tuning"
 */
const STAGE_LABEL_BY_NUMBER: Record<string, string> = {
  "1": "1: Baseline Implementation",
  "2": "2: Baseline Tuning",
  "3": "3: Creative Research",
  "4": "4: Ablation Studies",
  "5": "5: Paper Generation",
};

export function formatResearchStageName(stage: string | null | undefined): string | null {
  if (!stage) return null;
  const raw = stage.trim();
  if (!raw) return null;

  const stageNumber = extractStageNumber(raw);
  if (stageNumber) return STAGE_LABEL_BY_NUMBER[stageNumber] ?? raw;

  // Fallback: if we ever get an unexpected stage name, don't break UI—just show the raw value.
  return raw;
}

/**
 * Determines the current stage label for display in stats
 * Takes into account status, current stage, and progress to show the most appropriate label
 * @param status - Research run status
 * @param currentStage - Current pipeline stage
 * @param progress - Current progress (0-1)
 * @returns Display label for current stage
 */
export function getCurrentStageLabel(
  status: string,
  currentStage: string | null,
  progress: number | null
): string {
  // If explicitly completed or failed, show that status
  if (status === "completed") return "Completed";
  if (status === "failed") return "Failed";

  // Check if final stage is complete (stage 5 with 100% progress)
  const isFinalStageComplete =
    typeof currentStage === "string" &&
    currentStage.startsWith("5_") &&
    progress !== null &&
    progress !== undefined &&
    progress >= 1;

  if (isFinalStageComplete) return "Completed";

  // Format the current stage name
  return (formatResearchStageName(currentStage) ?? currentStage) || "Pending";
}

/**
 * Stage badge configuration for Open/Closed compliance
 */
export interface StageBadgeConfig {
  pattern: string;
  className: string;
}

/**
 * Default stage configurations for research pipeline stages
 */
export const DEFAULT_STAGE_CONFIGS: StageBadgeConfig[] = [
  { pattern: "baseline", className: "bg-purple-500/15 text-purple-400 border-purple-500/30" },
  { pattern: "tuning", className: "bg-blue-500/15 text-blue-400 border-blue-500/30" },
  { pattern: "plotting", className: "bg-cyan-500/15 text-cyan-400 border-cyan-500/30" },
  { pattern: "ablation", className: "bg-orange-500/15 text-orange-400 border-orange-500/30" },
];

/**
 * Returns human-readable status text based on status and current stage
 * @param status - Research run status string
 * @param currentStage - Current pipeline stage (optional)
 * @returns Human-readable status text
 */
export function getStatusText(status: string, currentStage: string | null): string {
  switch (status) {
    case "completed":
      return "Completed";
    case "initializing":
      return "Initializing";
    case "running":
      if (currentStage) {
        return `Running ${formatResearchStageName(currentStage) ?? currentStage}`;
      }
      return "Running";
    case "failed":
      return "Failed";
    case "pending":
      return "Waiting on ideation";
    default:
      return "Waiting on ideation";
  }
}

/**
 * Size configuration for status badges
 */
export type StatusBadgeSize = "sm" | "lg";

interface StatusBadgeSizeConfig {
  container: string;
  icon: string;
}

const STATUS_BADGE_SIZES: Record<StatusBadgeSize, StatusBadgeSizeConfig> = {
  sm: { container: "gap-1.5 px-3 py-1.5 text-xs", icon: "h-3.5 w-3.5" },
  lg: { container: "gap-2 w-28 justify-center py-1 text-sm", icon: "h-4 w-4" },
};

/**
 * Returns a styled status badge for a research run status
 * @param status - Research run status string
 * @param size - Badge size variant ("sm" | "lg"), defaults to "sm"
 * @returns React element with styled badge
 */
export function getStatusBadge(status: string, size: StatusBadgeSize = "sm") {
  const sizeConfig = STATUS_BADGE_SIZES[size];

  switch (status) {
    case "completed":
      return (
        <span
          className={`inline-flex items-center rounded-full bg-emerald-500/15 font-medium text-emerald-400 ${sizeConfig.container}`}
        >
          <CheckCircle2 className={sizeConfig.icon} />
          Completed
        </span>
      );
    case "initializing":
      return (
        <span
          className={`inline-flex items-center rounded-full bg-amber-500/15 font-medium text-amber-300 ${sizeConfig.container}`}
        >
          <Loader2 className={`animate-spin ${sizeConfig.icon}`} />
          Initializing
        </span>
      );
    case "running":
      return (
        <span
          className={`inline-flex items-center rounded-full bg-sky-500/15 font-medium text-sky-400 ${sizeConfig.container}`}
        >
          <Loader2 className={`animate-spin ${sizeConfig.icon}`} />
          Running
        </span>
      );
    case "failed":
      return (
        <span
          className={`inline-flex items-center rounded-full bg-red-500/15 font-medium text-red-400 ${sizeConfig.container}`}
        >
          <AlertCircle className={sizeConfig.icon} />
          Failed
        </span>
      );
    case "pending":
    default:
      return (
        <span
          className={`inline-flex items-center rounded-full bg-amber-500/15 font-medium text-amber-400 ${sizeConfig.container}`}
        >
          <Clock className={sizeConfig.icon} />
          Pending
        </span>
      );
  }
}

/**
 * Truncates a run ID to a maximum length
 * @param runId - The full run ID string
 * @param maxLength - Maximum length before truncation (default: 14)
 * @returns Truncated run ID with ellipsis if needed
 */
export function truncateRunId(runId: string, maxLength = 14): string {
  if (runId.length <= maxLength) return runId;
  return `${runId.slice(0, maxLength)}...`;
}

/**
 * Returns a styled stage badge for a research pipeline stage
 * @param stage - Pipeline stage string (baseline, tuning, plotting, ablation)
 * @param status - Optional run status to check for completed/failed states
 * @param configs - Optional custom stage configurations (Open/Closed compliant)
 * @returns React element with styled badge, or null if no stage
 */
export function getStageBadge(
  stage: string | null,
  status?: string | null,
  configs: StageBadgeConfig[] = DEFAULT_STAGE_CONFIGS
): ReactNode {
  // If status is completed, show "Completed" badge
  if (status === "completed") {
    return (
      <span className="inline-flex rounded-lg border px-2.5 py-1 text-xs font-medium bg-emerald-500/15 text-emerald-400 border-emerald-500/30">
        Completed
      </span>
    );
  }

  // If status is failed, show "Failed" badge
  if (status === "failed") {
    return (
      <span className="inline-flex rounded-lg border px-2.5 py-1 text-xs font-medium bg-red-500/15 text-red-400 border-red-500/30">
        Failed
      </span>
    );
  }

  if (!stage) return null;

  const matchedConfig = configs.find(config => stage.toLowerCase().includes(config.pattern));

  const colorClass =
    matchedConfig?.className ?? "bg-slate-500/15 text-slate-400 border-slate-500/30";

  const label = formatResearchStageName(stage) ?? stage;

  return (
    <span className={`inline-flex rounded-lg border px-2.5 py-1 text-xs font-medium ${colorClass}`}>
      {label}
    </span>
  );
}

/**
 * Log level color configuration for Open/Closed compliance
 */
const LOG_LEVEL_COLORS: Record<string, string> = {
  error: "text-red-400",
  warn: "text-amber-400",
  warning: "text-amber-400",
  info: "text-sky-400",
  debug: "text-slate-400",
};

/**
 * Returns the appropriate text color class for a log level
 * @param level - Log level string (error, warn, warning, info, debug)
 * @returns Tailwind CSS color class
 */
export function getLogLevelColor(level: string): string {
  return LOG_LEVEL_COLORS[level.toLowerCase()] ?? "text-slate-300";
}

/**
 * Replicates backend's progress calculation logic from research_pipeline_runs.py
 * Combines stage_progress and paper_generation_progress, then finds the latest event.
 *
 * This matches the SQL logic:
 * 1. UNION ALL of rp_run_stage_progress_events and rp_paper_generation_events
 * 2. ORDER BY created_at DESC to get latest event
 * 3. Calculate overall progress: (stage_number * 0.2) - (progress >= 1 ? 0 : 0.2)
 */
export function getCurrentStageAndProgress(
  stageProgress: StageProgress[],
  paperGenerationProgress: PaperGenerationEvent[]
): { currentStage: string | null; progress: number | null } {
  // Combine both sources (replicating the SQL UNION ALL)
  const allProgress: Array<{ stage: string; progress: number; created_at: string }> = [
    ...stageProgress.map(sp => ({
      stage: sp.stage,
      progress: sp.progress,
      created_at: sp.created_at,
    })),
    ...paperGenerationProgress.map(pg => ({
      stage: "5_paper_generation",
      progress: pg.progress,
      created_at: pg.created_at,
    })),
  ];

  // If no progress events, return nulls
  if (allProgress.length === 0) {
    return { currentStage: null, progress: null };
  }

  // Find the latest event by created_at (replicating DISTINCT ON ... ORDER BY created_at DESC)
  const latestEvent = allProgress.reduce((latest, current) => {
    return new Date(current.created_at) > new Date(latest.created_at) ? current : latest;
  });

  const currentStage = latestEvent.stage;
  const stageProgressValue = latestEvent.progress;

  // Calculate overall progress (replicating the CASE statement)
  const stageNumberMatch = currentStage.match(/^([1-5])_/);
  let overallProgress: number;

  if (stageNumberMatch && stageNumberMatch[1]) {
    const stageNumber = parseInt(stageNumberMatch[1], 10);
    // Formula: (stage_number * 0.2) - (progress >= 1 ? 0 : 0.2)
    overallProgress = stageNumber * 0.2 - (stageProgressValue >= 1 ? 0 : 0.2);
  } else {
    // Fallback: use raw progress
    overallProgress = stageProgressValue;
  }

  return {
    currentStage,
    progress: Math.max(0, Math.min(1, overallProgress)),
  };
}
