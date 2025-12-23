/**
 * Research-specific utility functions
 */
import type { ReactNode } from "react";
import { CheckCircle2, Clock, Loader2, AlertCircle } from "lucide-react";

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

function extractLeadingStageNumber(stage: string): string | null {
  const match = stage.match(/^(\d+)(?:_|$)/);
  return match?.[1] ?? null;
}

export function formatResearchStageName(stage: string | null | undefined): string | null {
  if (!stage) return null;
  const raw = stage.trim();
  if (!raw) return null;

  const stageNumber = extractLeadingStageNumber(raw);
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
  lg: { container: "gap-2 px-4 py-2 text-sm", icon: "h-5 w-5" },
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
