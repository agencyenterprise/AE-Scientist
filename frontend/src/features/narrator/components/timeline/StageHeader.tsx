/**
 * StageHeader - Sticky header for a stage section with metadata and controls.
 */

import type { StageGroup } from "@/features/narrator/lib/narratorSelectors";
import { formatTimeRange } from "@/features/narrator/lib/eventGrouping";
import { ChevronDown, ChevronRight, Activity } from "lucide-react";
import { cn } from "@/shared/lib/utils";

interface StageHeaderProps {
  stage: StageGroup;
  stageIndex: number;
  isExpanded: boolean;
  onToggle: () => void;
}

export function StageHeader({ stage, isExpanded, onToggle }: StageHeaderProps) {
  const { stageGoal, status, progress, activeNodeCount, timeRange, events } = stage;

  // Status styling
  const statusConfig = {
    pending: {
      icon: "⏳",
      label: "Pending",
      color: "text-slate-400",
      bgColor: "bg-slate-500/10",
    },
    running: {
      icon: "▶️",
      label: "Running",
      color: "text-blue-400",
      bgColor: "bg-blue-500/10",
    },
    completed: {
      icon: "✅",
      label: "Completed",
      color: "text-green-400",
      bgColor: "bg-green-500/10",
    },
    failed: {
      icon: "❌",
      label: "Failed",
      color: "text-red-400",
      bgColor: "bg-red-500/10",
    },
    in_progress: {
      icon: "▶️",
      label: "In Progress",
      color: "text-blue-400",
      bgColor: "bg-blue-500/10",
    },
    skipped: {
      icon: "⏭️",
      label: "Skipped",
      color: "text-gray-400",
      bgColor: "bg-slate-500/10",
    },
  };

  const config = statusConfig[status];

  // Calculate duration
  const duration =
    timeRange.start && timeRange.end ? formatTimeRange(timeRange.start, timeRange.end) : null;

  return (
    <div
      className={cn("bg-slate-900/70 backdrop-blur-sm border-y border-slate-700/80")}
      data-sticky-header
      data-stage-id={stage.stageId}
    >
      <button
        onClick={onToggle}
        className="w-full text-left px-4 py-3 hover:bg-slate-800/50 transition-colors"
      >
        <div className="flex items-start justify-between gap-4">
          {/* Left: Title and metadata */}
          <div className="flex-1 min-w-0">
            {/* Title row */}
            <div className="flex items-center gap-2 mb-2">
              {/* Expand/collapse icon */}
              {isExpanded ? (
                <ChevronDown className="w-4 h-4 text-slate-400 flex-shrink-0" />
              ) : (
                <ChevronRight className="w-4 h-4 text-slate-400 flex-shrink-0" />
              )}

              {/* Stage title */}
              <h3 className="text-base font-semibold text-white truncate">
                {stageGoal?.title || stage.stageId}
              </h3>

              {/* Status badge */}
              <span
                className={`flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium ${config.bgColor} ${config.color} flex-shrink-0`}
              >
                <span role="img" aria-label={config.label}>
                  {config.icon}
                </span>
                {config.label}
              </span>
            </div>

            {/* Metadata row */}
            <div className="flex items-center gap-3 text-xs text-slate-400 ml-6">
              {/* Event count */}
              <span>{events.length} events</span>

              {/* Duration */}
              {duration && <span>• {duration}</span>}

              {/* Active nodes */}
              {activeNodeCount > 0 && (
                <span className="flex items-center gap-1 text-blue-400">
                  <Activity className="w-3 h-3" />
                  {activeNodeCount} active
                </span>
              )}
            </div>

            {/* Goal (if available and not too long) */}
            {stageGoal?.goal && isExpanded && (
              <p className="text-xs text-slate-400 mt-2 ml-6 line-clamp-2">{stageGoal.goal}</p>
            )}
          </div>

          {/* Right: Progress indicator */}
          {status !== "pending" && (
            <div className="flex-shrink-0 w-24">
              <div className="text-right mb-1">
                <span className="text-xs font-semibold text-slate-300">
                  {Math.round(progress * 100)}%
                </span>
              </div>
              <div className="h-1.5 bg-slate-700/50 rounded-full overflow-hidden">
                <div
                  className={`h-full transition-all duration-500 ${
                    status === "completed" ? "bg-green-500" : "bg-blue-500"
                  }`}
                  style={{ width: `${Math.round(progress * 100)}%` }}
                />
              </div>
            </div>
          )}
        </div>
      </button>
    </div>
  );
}
