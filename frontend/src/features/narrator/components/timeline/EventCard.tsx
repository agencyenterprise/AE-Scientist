/**
 * EventCard - Displays a single timeline event with compact, action-oriented design.
 */

import type { components } from "@/types/api.gen";
import {
  getEventTypeLabel,
  getEventTypeIcon,
  getEventTypeColor,
  formatTimestamp,
} from "@/features/narrator/lib/eventGrouping";
import { Card, CardContent } from "@/shared/components/ui/card";
import { Button } from "@/shared/components/ui/button";
import { ExternalLink } from "lucide-react";

type ResearchRunState = components["schemas"]["ResearchRunState"];
type TimelineEvent = NonNullable<ResearchRunState["timeline"]>[number];

interface EventCardProps {
  event: TimelineEvent;
  compact?: boolean;
  onViewNode?: (nodeId: string) => void;
  onEventFocus?: (eventId: string | null) => void;
}

export function EventCard({ event, compact = false, onViewNode, onEventFocus }: EventCardProps) {
  const typeLabel = getEventTypeLabel(event.type);
  const typeIcon = getEventTypeIcon(event.type);
  const typeColor = getEventTypeColor(event.type);
  const timestamp = formatTimestamp(event.timestamp);

  const handleClick = () => {
    if (onEventFocus && event.id) {
      onEventFocus(event.id);
    }
  };

  return (
    <Card
      className={`border ${typeColor} ${compact ? "py-3" : ""} cursor-pointer transition-all hover:border-opacity-60`}
      onClick={handleClick}
      data-event-id={event.id}
    >
      <CardContent className={compact ? "py-0" : ""}>
        {/* Header: Type badge + Timestamp */}
        <div className="flex items-start justify-between gap-4 mb-2">
          <div className="flex items-center gap-2">
            <span className="text-lg" role="img" aria-label={typeLabel}>
              {typeIcon}
            </span>
            <span className="text-sm font-semibold">{typeLabel}</span>
          </div>
          <span className="text-xs text-slate-400 whitespace-nowrap">{timestamp}</span>
        </div>

        {/* Headline */}
        {event.headline && (
          <p className="text-sm text-slate-200 mb-2 line-clamp-2">{event.headline}</p>
        )}

        {/* Event-specific content */}
        <EventContent event={event} compact={compact} />

        {/* Actions */}
        {event.node_id && onViewNode && (
          <div className="mt-3 pt-3 border-t border-slate-700/50">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => onViewNode(event.node_id!)}
              className="h-7 text-xs"
            >
              <ExternalLink className="w-3 h-3 mr-1" />
              View in Tree
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

/**
 * Render event-specific content based on event type.
 */
function EventContent({ event, compact }: { event: TimelineEvent; compact: boolean }) {
  const textClass = compact ? "text-xs" : "text-sm";

  switch (event.type) {
    case "run_started":
      return (
        <div className={`${textClass} text-slate-300 space-y-1`}>
          {"gpu_type" in event && event.gpu_type && (
            <p className="font-medium">GPU: {event.gpu_type}</p>
          )}
          {"cost_per_hour_cents" in event &&
            event.cost_per_hour_cents !== undefined &&
            event.cost_per_hour_cents !== null && (
              <p className="text-slate-400">
                Cost: ${(event.cost_per_hour_cents / 100).toFixed(2)}/hour
              </p>
            )}
        </div>
      );

    case "stage_started":
      return (
        <div className={`${textClass} text-slate-300 space-y-1`}>
          {"stage_name" in event && event.stage_name && (
            <p className="font-medium">{event.stage_name}</p>
          )}
          {"goal" in event && event.goal && <p className="text-slate-400">{event.goal}</p>}
        </div>
      );

    case "stage_completed":
      return (
        <div className={`${textClass} text-slate-300 space-y-2`}>
          {"summary" in event && event.summary && <p>{event.summary}</p>}
        </div>
      );

    case "progress_update":
      return (
        <div className={`${textClass} text-slate-300`}>
          {"iteration" in event && "max_iterations" in event && (
            <p>
              Iteration {event.iteration} / {event.max_iterations}
              {"current_focus" in event && event.current_focus && (
                <span className="text-slate-400 ml-2">• {event.current_focus}</span>
              )}
            </p>
          )}
        </div>
      );

    case "node_result":
      return (
        <div className={`${textClass} text-slate-300 space-y-1`}>
          {"outcome" in event && event.outcome && (
            <p>
              Outcome: <span className="font-semibold text-slate-200">{event.outcome}</span>
            </p>
          )}
          {"summary" in event && event.summary && !compact && (
            <p className="text-slate-400 line-clamp-2">{event.summary}</p>
          )}
          {"error_summary" in event && event.error_summary && (
            <p className="text-red-400 line-clamp-2">{event.error_summary}</p>
          )}
        </div>
      );

    case "node_execution_started":
      return (
        <div className={`${textClass} text-slate-300`}>
          {"execution_id" in event && event.execution_id && (
            <p className="font-mono text-xs text-slate-400">
              ID: {event.execution_id.slice(0, 8)}...
            </p>
          )}
        </div>
      );

    case "node_execution_completed":
      return (
        <div className={`${textClass} text-slate-300`}>
          {"status" in event && event.status && (
            <p>
              Status: <span className="font-semibold text-slate-200">{event.status}</span>
              {"exec_time" in event && event.exec_time && (
                <span className="text-slate-400 ml-2">• {event.exec_time}s</span>
              )}
            </p>
          )}
        </div>
      );

    case "paper_generation_step":
      return (
        <div className={`${textClass} text-slate-300`}>
          {"step" in event && typeof event.step === "string" ? (
            <p className="font-medium">{event.step}</p>
          ) : null}
          {"progress" in event && event.progress !== undefined && event.progress !== null && (
            <p className="text-slate-400">Progress: {Math.round(event.progress * 100)}%</p>
          )}
        </div>
      );

    case "run_finished":
      return (
        <div className={`${textClass} text-slate-300 space-y-2`}>
          {"status" in event && event.status && (
            <div className="flex items-center gap-2">
              <span
                className={`inline-block px-2 py-1 rounded text-xs font-semibold ${
                  event.success
                    ? "bg-emerald-900/50 text-emerald-200"
                    : "bg-red-900/50 text-red-200"
                }`}
              >
                {event.status.toUpperCase()}
              </span>
              {"reason" in event && event.reason && (
                <span className="text-xs text-slate-400">({event.reason})</span>
              )}
            </div>
          )}
          {"summary" in event && event.summary && <p>{event.summary}</p>}
          {"message" in event && event.message && !("summary" in event && event.summary) && (
            <p className="text-slate-400">{event.message}</p>
          )}
          {!compact && (
            <div className="grid grid-cols-2 gap-2 text-xs text-slate-400 mt-2 pt-2 border-t border-slate-700/50">
              {"stages_completed" in event && event.stages_completed !== undefined && (
                <div>
                  <span className="font-medium">Stages:</span> {event.stages_completed}
                </div>
              )}
              {"total_nodes_executed" in event && event.total_nodes_executed !== undefined && (
                <div>
                  <span className="font-medium">Nodes:</span> {event.total_nodes_executed}
                </div>
              )}
              {"total_duration_seconds" in event &&
                event.total_duration_seconds !== undefined &&
                event.total_duration_seconds !== null && (
                  <div className="col-span-2">
                    <span className="font-medium">Duration:</span>{" "}
                    {formatDuration(event.total_duration_seconds)}
                  </div>
                )}
            </div>
          )}
        </div>
      );

    default:
      return null;
  }
}

/**
 * Format duration in seconds to human-readable string.
 */
function formatDuration(seconds: number): string {
  if (seconds < 60) {
    return `${Math.round(seconds)}s`;
  }
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = Math.round(seconds % 60);
  if (minutes < 60) {
    return remainingSeconds > 0 ? `${minutes}m ${remainingSeconds}s` : `${minutes}m`;
  }
  const hours = Math.floor(minutes / 60);
  const remainingMinutes = minutes % 60;
  if (hours < 24) {
    return remainingMinutes > 0 ? `${hours}h ${remainingMinutes}m` : `${hours}h`;
  }
  const days = Math.floor(hours / 24);
  const remainingHours = hours % 24;
  return remainingHours > 0 ? `${days}d ${remainingHours}h` : `${days}d`;
}
