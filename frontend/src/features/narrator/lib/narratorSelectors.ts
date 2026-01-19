/**
 * Pure selector functions for narrator state.
 * Use these in components instead of storing computed values in Zustand.
 */

import type { components } from "@/types/api.gen";

// Use generated types from OpenAPI schema
type ResearchRunState = components["schemas"]["ResearchRunState"];
type TimelineEvent = NonNullable<ResearchRunState["timeline"]>[number];

export function getCurrentStage(state: ResearchRunState | null): string | null {
  return state?.current_stage ?? null;
}

export function getCurrentFocus(state: ResearchRunState | null): string | null {
  return state?.current_focus ?? null;
}

export function getOverallProgress(state: ResearchRunState | null): number {
  return state?.overall_progress ?? 0;
}

export function getStatus(state: ResearchRunState | null): string | null {
  return state?.status ?? null;
}

export function getRunId(state: ResearchRunState | null): string | null {
  return state?.run_id ?? null;
}

export function isRunComplete(state: ResearchRunState | null): boolean {
  return state?.status === "completed";
}

export function isRunFailed(state: ResearchRunState | null): boolean {
  return state?.status === "failed";
}

export function isRunRunning(state: ResearchRunState | null): boolean {
  return state?.status === "running";
}

export function formatProgress(progress: number): string {
  return `${Math.round(progress * 100)}%`;
}

export function getEventsByStage(events: TimelineEvent[], stageId: string): TimelineEvent[] {
  return events.filter(event => event.stage === stageId);
}

export function getLatestEvent(events: TimelineEvent[]): TimelineEvent | null {
  return events.length > 0 ? (events[events.length - 1] ?? null) : null;
}

// ============================================================================
// Stage Grouping Selectors
// ============================================================================

export type StageGoal = NonNullable<ResearchRunState["stages"]>[number];
type StageStatus = StageGoal["status"];

export interface StageGroup {
  stageId: string;
  stageGoal: StageGoal | null;
  events: TimelineEvent[];
  status: StageStatus;
  progress: number;
  activeNodeCount: number;
  timeRange: {
    start: string | null;
    end: string | null;
  };
}

/**
 * Group timeline events by stage, maintaining chronological order.
 * Returns stages in the order they appear in state.stages.
 */
export function groupEventsByStage(state: ResearchRunState | null): StageGroup[] {
  if (!state) return [];

  const stages = state.stages || [];
  const events = state.timeline || [];
  const currentStage = state.current_stage;
  const activeNodes = state.active_nodes || [];

  // Group events by stage ID
  const eventsByStage = new Map<string, TimelineEvent[]>();
  for (const event of events) {
    if (!event.stage) continue;
    const stageEvents = eventsByStage.get(event.stage) || [];
    stageEvents.push(event);
    eventsByStage.set(event.stage, stageEvents);
  }

  // Build stage groups in order
  return stages.map(stageGoal => {
    const stageId = stageGoal.stage;
    const stageEvents = eventsByStage.get(stageId) || [];

    // Determine stage status
    let status: StageGroup["status"] = "pending";
    if (stageGoal.status) {
      status = stageGoal.status as StageGroup["status"];
    } else if (currentStage === stageId) {
      status = "in_progress";
    } else if (stageEvents.length > 0) {
      // Check if stage has completed event
      const hasCompleted = stageEvents.some(e => e.type === "stage_completed");
      status = hasCompleted ? "completed" : "in_progress";
    }

    // Calculate time range
    const timeRange = {
      start: stageEvents.length > 0 ? stageEvents[0]?.timestamp || null : null,
      end: stageEvents.length > 0 ? stageEvents[stageEvents.length - 1]?.timestamp || null : null,
    };

    // Count active nodes for this stage
    const activeNodeCount = activeNodes.filter(node => node.stage === stageId).length;

    return {
      stageId,
      stageGoal,
      events: stageEvents,
      status,
      progress: stageGoal.progress || 0,
      activeNodeCount,
      timeRange,
    };
  });
}

/**
 * Get metadata for a specific stage.
 */
export function getStageMetadata(
  state: ResearchRunState | null,
  stageId: string
): Omit<StageGroup, "events"> | null {
  const groups = groupEventsByStage(state);
  const group = groups.find(g => g.stageId === stageId);
  if (!group) return null;

  const { events: _events, ...metadata } = group;
  return metadata;
}

/**
 * Get all stages with their goals (no events).
 */
export function getStages(state: ResearchRunState | null): StageGoal[] {
  return state?.stages || [];
}

/**
 * Get a specific stage goal by ID.
 */
export function getStageGoal(state: ResearchRunState | null, stageId: string): StageGoal | null {
  const stages = getStages(state);
  return stages.find(s => s.stage === stageId) || null;
}
