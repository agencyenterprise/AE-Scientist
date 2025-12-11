"use client";

import type { PaperGenerationEvent } from "@/types/research";
import { Tooltip, TooltipTrigger, TooltipContent } from "@/shared/components/ui/tooltip";
import { format } from "date-fns";

interface PaperGenerationProgressProps {
  events: PaperGenerationEvent[];
}

const STEP_LABELS: Record<string, string> = {
  plot_aggregation: "Plot Aggregation",
  citation_gathering: "Citation Gathering",
  paper_writeup: "Paper Writeup",
  paper_review: "Paper Review",
};

const STEP_DESCRIPTIONS: Record<string, string> = {
  plot_aggregation: "Aggregating and validating plots from experiments",
  citation_gathering: "Gathering relevant citations and references",
  paper_writeup: "Writing paper content and formatting",
  paper_review: "Conducting peer review and refinement",
};

const STEP_ORDER = ["plot_aggregation", "citation_gathering", "paper_writeup", "paper_review"];

export function PaperGenerationProgress({ events }: PaperGenerationProgressProps) {
  if (events.length === 0) {
    return <div className="text-sm text-slate-500 italic">No paper generation events yet</div>;
  }

  // Get the latest event to show overall progress
  // Safe to assert non-null since we return early if events.length === 0
  const latestEvent = events[events.length - 1]!;

  // Get unique steps from events
  const eventsByStep = new Map<string, PaperGenerationEvent[]>();
  events.forEach(event => {
    if (!eventsByStep.has(event.step)) {
      eventsByStep.set(event.step, []);
    }
    eventsByStep.get(event.step)!.push(event);
  });

  // Render each step in order
  const renderedSteps = STEP_ORDER.map(step => {
    const stepEvents = eventsByStep.get(step) || [];
    const isActive = latestEvent.step === step;
    const isCompleted = STEP_ORDER.indexOf(step) < STEP_ORDER.indexOf(latestEvent.step);

    if (stepEvents.length === 0 && !isCompleted && !isActive) {
      return null;
    }

    const latestStepEvent = stepEvents[stepEvents.length - 1];
    const progressPercent = latestStepEvent ? Math.round(latestStepEvent.step_progress * 100) : 0;

    return (
      <div key={step} className="space-y-2 mb-4">
        {/* Step Header */}
        <div className="flex items-start justify-between">
          <div>
            <h4 className="font-medium text-sm">
              {isActive && (
                <span className="inline-block w-2 h-2 bg-blue-500 rounded-full mr-2 animate-pulse"></span>
              )}
              {isCompleted && (
                <span className="inline-block w-2 h-2 bg-green-500 rounded-full mr-2"></span>
              )}
              {!isActive && !isCompleted && (
                <span className="inline-block w-2 h-2 bg-slate-300 rounded-full mr-2"></span>
              )}
              {STEP_LABELS[step]}
            </h4>
            <p className="text-xs text-slate-500">{STEP_DESCRIPTIONS[step]}</p>
          </div>
          {latestStepEvent && (
            <div className="text-xs text-slate-600">
              {format(new Date(latestStepEvent.created_at), "HH:mm:ss")}
            </div>
          )}
        </div>

        {/* Progress Bar */}
        {stepEvents.length > 0 && (
          <div className="space-y-1">
            <div className="w-full bg-slate-200 rounded-full h-2 overflow-hidden">
              <div
                className={`h-full transition-all duration-300 ${
                  isCompleted ? "bg-green-500" : isActive ? "bg-blue-500" : "bg-slate-300"
                }`}
                style={{ width: `${progressPercent}%` }}
              />
            </div>
            <div className="flex justify-between text-xs text-slate-600">
              <span>{progressPercent}% complete</span>
              {latestStepEvent?.substep && (
                <span className="text-slate-500">{latestStepEvent.substep}</span>
              )}
            </div>
          </div>
        )}

        {/* Details */}
        {latestStepEvent?.details && (
          <Tooltip>
            <TooltipTrigger asChild>
              <div className="text-xs text-slate-500 cursor-help border-l-2 border-slate-300 pl-2">
                {Object.entries(latestStepEvent.details)
                  .slice(0, 2)
                  .map(([key, value]) => (
                    <div key={key}>
                      {key}: {String(value)}
                    </div>
                  ))}
                {Object.keys(latestStepEvent.details).length > 2 && (
                  <div>+{Object.keys(latestStepEvent.details).length - 2} more</div>
                )}
              </div>
            </TooltipTrigger>
            <TooltipContent>
              <div className="space-y-1">
                {Object.entries(latestStepEvent.details).map(([key, value]) => (
                  <div key={key} className="text-xs">
                    <span className="font-medium">{key}:</span> {String(value)}
                  </div>
                ))}
              </div>
            </TooltipContent>
          </Tooltip>
        )}

        {/* Event Timeline */}
        {stepEvents.length > 1 && (
          <div className="text-xs text-slate-500 space-y-1">
            <details className="cursor-pointer">
              <summary>{stepEvents.length} events in this step</summary>
              <div className="pl-4 mt-2 space-y-1 border-l-2 border-slate-200">
                {stepEvents.map((event, idx) => (
                  <div key={idx} className="text-xs text-slate-600">
                    <span>
                      {Math.round(event.step_progress * 100)}% -
                      {event.substep ? ` ${event.substep} ` : " "}
                      {format(new Date(event.created_at), "HH:mm:ss")}
                    </span>
                  </div>
                ))}
              </div>
            </details>
          </div>
        )}
      </div>
    );
  }).filter(Boolean);

  return (
    <div className="space-y-6">
      {/* Overall Progress Header */}
      <div className="bg-slate-50 p-4 rounded-lg border border-slate-200">
        <div className="flex items-center justify-between mb-3">
          <h3 className="font-semibold text-sm">Paper Generation Progress</h3>
          <div className="text-right">
            <div className="text-2xl font-bold text-blue-600">
              {Math.round(latestEvent.progress * 100)}%
            </div>
            <div className="text-xs text-slate-500">overall progress</div>
          </div>
        </div>

        {/* Main Progress Bar */}
        <div className="w-full bg-slate-200 rounded-full h-3 overflow-hidden">
          <div
            className="h-full bg-blue-500 transition-all duration-300"
            style={{ width: `${Math.round(latestEvent.progress * 100)}%` }}
          />
        </div>

        {/* Current Step Indicator */}
        <div className="mt-3 text-sm text-slate-700">
          Current step: <span className="font-medium">{STEP_LABELS[latestEvent.step]}</span>
        </div>
      </div>

      {/* Steps */}
      <div className="space-y-4">{renderedSteps}</div>
    </div>
  );
}
