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

export function getEventsByStage(
  events: TimelineEvent[],
  stageId: string
): TimelineEvent[] {
  return events.filter((event) => event.stage === stageId);
}

export function getLatestEvent(events: TimelineEvent[]): TimelineEvent | null {
  return events.length > 0 ? events[events.length - 1] ?? null : null;
}

