/**
 * Research-specific utility functions
 */
import { CheckCircle2, Clock, Loader2, AlertCircle } from "lucide-react";

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
 * Returns a styled status badge for a research run status
 * @param status - Research run status string
 * @returns React element with styled badge
 */
export function getStatusBadge(status: string) {
  switch (status) {
    case "completed":
      return (
        <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-500/15 px-3 py-1.5 text-xs font-medium text-emerald-400">
          <CheckCircle2 className="h-3.5 w-3.5" />
          Completed
        </span>
      );
    case "running":
      return (
        <span className="inline-flex items-center gap-1.5 rounded-full bg-sky-500/15 px-3 py-1.5 text-xs font-medium text-sky-400">
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
          Running
        </span>
      );
    case "failed":
      return (
        <span className="inline-flex items-center gap-1.5 rounded-full bg-red-500/15 px-3 py-1.5 text-xs font-medium text-red-400">
          <AlertCircle className="h-3.5 w-3.5" />
          Failed
        </span>
      );
    case "pending":
    default:
      return (
        <span className="inline-flex items-center gap-1.5 rounded-full bg-amber-500/15 px-3 py-1.5 text-xs font-medium text-amber-400">
          <Clock className="h-3.5 w-3.5" />
          Pending
        </span>
      );
  }
}
