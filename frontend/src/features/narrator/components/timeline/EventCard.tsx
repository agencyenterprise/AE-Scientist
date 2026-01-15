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

    default:
      return null;
  }
}
