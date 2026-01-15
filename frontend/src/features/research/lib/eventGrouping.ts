/**
 * Event grouping algorithm - Pure functions for detecting and grouping similar events.
 * 
 * Purpose: Detect sequences of repetitive events (e.g., 300 progress updates during
 * a 5-hour code execution) and group them for better UX.
 */

import type { components } from "@/types/api.gen";

type ResearchRunState = components["schemas"]["ResearchRunState"];
type TimelineEvent = NonNullable<ResearchRunState["timeline"]>[number];

export interface SingleEventItem {
  type: "single";
  event: TimelineEvent;
}

export interface GroupedEventItem {
  type: "grouped";
  events: TimelineEvent[]; // Chronologically ordered, latest last
  latestEvent: TimelineEvent;
  count: number;
}

export type EventItem = SingleEventItem | GroupedEventItem;

/**
 * Group similar consecutive events together.
 * 
 * Algorithm:
 * 1. Iterate through events chronologically
 * 2. If event is similar to previous group, add it
 * 3. Otherwise, finalize previous group and start new one
 * 4. Only group if we have 2+ similar events
 * 
 * @param events Timeline events (should be chronologically sorted)
 * @returns Array of single or grouped event items
 */
export function groupSimilarEvents(events: TimelineEvent[]): EventItem[] {
  if (events.length === 0) return [];

  const items: EventItem[] = [];
  let currentGroup: TimelineEvent[] = [];

  for (const event of events) {
    if (shouldGroupWith(event, currentGroup)) {
      currentGroup.push(event);
    } else {
      // Finalize previous group
      if (currentGroup.length > 0) {
        items.push(finalizeGroup(currentGroup));
      }
      // Start new group
      currentGroup = [event];
    }
  }

  // Finalize last group
  if (currentGroup.length > 0) {
    items.push(finalizeGroup(currentGroup));
  }

  return items;
}

/**
 * Determine if an event should be grouped with the current group.
 */
function shouldGroupWith(
  event: TimelineEvent,
  group: TimelineEvent[]
): boolean {
  if (group.length === 0) return false;

  const lastEvent = group[group.length - 1];
  if (!lastEvent) return false;

  // Must be same type and stage
  if (event.type !== lastEvent.type || event.stage !== lastEvent.stage) {
    return false;
  }

  // Check if events are consecutive (within 10 minutes)
  const timeDiff = getTimeDiffMinutes(lastEvent.timestamp, event.timestamp);
  if (timeDiff > 10) {
    return false;
  }

  // Type-specific grouping rules
  return shouldGroupByType(event, lastEvent);
}

/**
 * Type-specific grouping rules.
 */
function shouldGroupByType(
  event: TimelineEvent,
  lastEvent: TimelineEvent
): boolean {
  switch (event.type) {
    case "progress_update":
      // Group progress updates from same stage
      return true;

    case "node_execution_started":
    case "node_execution_completed":
      // Group node executions if they're rapid-fire
      return true;

    case "node_result":
      // Group node results if they have similar outcomes
      if ("outcome" in event && "outcome" in lastEvent) {
        return event.outcome === lastEvent.outcome;
      }
      return true;

    case "paper_generation_step":
      // Group paper generation steps
      return true;

    case "stage_started":
    case "stage_completed":
      // Never group stage transitions (important milestones)
      return false;

    default:
      return false;
  }
}

/**
 * Finalize a group of events into a single or grouped item.
 */
function finalizeGroup(group: TimelineEvent[]): EventItem {
  if (group.length === 1) {
    return {
      type: "single",
      event: group[0]!,
    };
  }

  const latestEvent = group[group.length - 1]!;

  return {
    type: "grouped",
    events: group,
    latestEvent,
    count: group.length,
  };
}

/**
 * Calculate time difference in minutes between two timestamps.
 */
function getTimeDiffMinutes(timestamp1: string, timestamp2: string): number {
  const date1 = new Date(timestamp1);
  const date2 = new Date(timestamp2);
  const diffMs = Math.abs(date2.getTime() - date1.getTime());
  return diffMs / (1000 * 60);
}

/**
 * Format time range for display.
 */
export function formatTimeRange(start: string, end: string): string {
  const startDate = new Date(start);
  const endDate = new Date(end);
  const diffMs = endDate.getTime() - startDate.getTime();

  const hours = Math.floor(diffMs / (1000 * 60 * 60));
  const minutes = Math.floor((diffMs % (1000 * 60 * 60)) / (1000 * 60));

  if (hours > 0) {
    return `${hours}h ${minutes}m`;
  }
  return `${minutes}m`;
}

/**
 * Format timestamp for display.
 */
export function formatTimestamp(timestamp: string): string {
  return new Date(timestamp).toLocaleTimeString(undefined, {
    hour: "2-digit",
    minute: "2-digit",
  });
}

/**
 * Get event type display name.
 */
export function getEventTypeLabel(type: string): string {
  const labels: Record<string, string> = {
    stage_started: "Stage Started",
    stage_completed: "Stage Completed",
    progress_update: "Progress Update",
    node_result: "Node Result",
    node_execution_started: "Execution Started",
    node_execution_completed: "Execution Completed",
    paper_generation_step: "Paper Generation",
  };

  return labels[type] || type;
}

/**
 * Get event type icon/emoji.
 */
export function getEventTypeIcon(type: string): string {
  const icons: Record<string, string> = {
    stage_started: "🚀",
    stage_completed: "✅",
    progress_update: "🔄",
    node_result: "📊",
    node_execution_started: "▶️",
    node_execution_completed: "⏹️",
    paper_generation_step: "📝",
  };

  return icons[type] || "•";
}

/**
 * Get event type color class.
 */
export function getEventTypeColor(type: string): string {
  const colors: Record<string, string> = {
    stage_started: "bg-blue-500/10 text-blue-400 border-blue-500/20",
    stage_completed: "bg-green-500/10 text-green-400 border-green-500/20",
    progress_update: "bg-purple-500/10 text-purple-400 border-purple-500/20",
    node_result: "bg-yellow-500/10 text-yellow-400 border-yellow-500/20",
    node_execution_started: "bg-cyan-500/10 text-cyan-400 border-cyan-500/20",
    node_execution_completed: "bg-teal-500/10 text-teal-400 border-teal-500/20",
    paper_generation_step: "bg-pink-500/10 text-pink-400 border-pink-500/20",
  };

  return colors[type] || "bg-gray-500/10 text-gray-400 border-gray-500/20";
}

