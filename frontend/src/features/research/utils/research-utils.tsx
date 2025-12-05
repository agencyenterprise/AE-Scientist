/**
 * Research-specific utility functions
 */
import type { ReactNode } from "react";
import { CheckCircle2, Clock, Loader2, AlertCircle } from "lucide-react";

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
        return `Running ${currentStage}`;
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
 * @param configs - Optional custom stage configurations (Open/Closed compliant)
 * @returns React element with styled badge, or null if no stage
 */
export function getStageBadge(
  stage: string | null,
  configs: StageBadgeConfig[] = DEFAULT_STAGE_CONFIGS
): ReactNode {
  if (!stage) return null;

  const matchedConfig = configs.find(config => stage.toLowerCase().includes(config.pattern));

  const colorClass =
    matchedConfig?.className ?? "bg-slate-500/15 text-slate-400 border-slate-500/30";

  return (
    <span className={`inline-flex rounded-lg border px-2.5 py-1 text-xs font-medium ${colorClass}`}>
      {stage}
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
