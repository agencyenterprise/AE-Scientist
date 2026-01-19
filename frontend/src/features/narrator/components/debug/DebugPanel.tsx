"use client";

import { ResearchRunState } from "@/features/narrator/systems/resources/narratorStore";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/shared/components/ui/tabs";
import { isDevelopment } from "@/shared/lib/config";
import { ChevronDown, ChevronUp, Bug } from "lucide-react";
import { useState } from "react";

interface DebugPanelProps {
  state: ResearchRunState | null;
}

export function DebugPanel({ state }: DebugPanelProps) {
  const [isOpen, setIsOpen] = useState(false);

  // Don't render in production
  if (!isDevelopment) {
    return null;
  }

  if (!state) {
    return (
      <div className="fixed bottom-4 right-4 bg-slate-900/95 border border-slate-700/80 rounded-lg shadow-2xl backdrop-blur-sm">
        <button
          onClick={() => setIsOpen(!isOpen)}
          className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-slate-300 hover:text-white transition-colors"
        >
          <Bug className="w-4 h-4" />
          <span>Debug Panel</span>
        </button>
        <div className="px-4 pb-3 text-xs text-slate-400">No state available</div>
      </div>
    );
  }

  const timeline = state.timeline || [];
  const stages = state.stages || [];

  // General stats
  const stats = {
    runId: state.run_id,
    conversationId: state.conversation_id,
    status: state.status,
    currentStage: state.current_stage,
    currentFocus: state.current_focus,
    overallProgress: `${state.overall_progress * 100}%`,
    timelineEventCount: timeline.length || "N/A",
    stateVersion: state.version,
    hypothesis: state.hypothesis ?? "N/A",
    startedRunningAt: state.started_running_at ?? "N/A",
    completedAt: state.completed_at ?? "N/A",
    gpuType: state.gpu_type ?? "N/A",
    estimatedCostCents: state.estimated_cost_cents ?? "N/A",
    actualCostCents: state.actual_cost_cents ?? "N/A",
    costPerHourCents: state.cost_per_hour_cents ?? "N/A",
    errorMessage: state.error_message ?? "N/A",
  };

  return (
    <div
      className={`fixed bottom-4 right-4 bg-slate-900/95 border border-slate-700/80 rounded-lg shadow-2xl backdrop-blur-sm transition-all duration-300 z-50 ${
        isOpen ? "w-[600px]" : "w-auto"
      }`}
    >
      {/* Header */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center justify-between w-full px-4 py-2 text-sm font-medium text-slate-300 hover:text-white transition-colors"
      >
        <div className="flex items-center gap-2">
          <Bug className="w-4 h-4" />
          <span>Debug Panel</span>
          <span className="text-xs text-slate-500">({timeline.length} events)</span>
        </div>
        {isOpen ? <ChevronDown className="w-4 h-4" /> : <ChevronUp className="w-4 h-4" />}
      </button>

      {/* Content */}
      {isOpen && (
        <div className="border-t border-slate-700/80">
          <Tabs defaultValue="general" className="p-4">
            <TabsList>
              <TabsTrigger value="general">General</TabsTrigger>
              <TabsTrigger value="stages">Stages ({stages.length})</TabsTrigger>
              <TabsTrigger value="timeline">Timeline ({timeline.length})</TabsTrigger>
            </TabsList>

            {/* General Tab */}
            <TabsContent value="general" className="mt-4">
              <div className="space-y-3 max-h-[400px] overflow-auto pr-2">
                <h3 className="text-sm font-semibold text-white mb-2">Overall Stats</h3>
                <div className="space-y-2">
                  {Object.entries(stats).map(([key, value]) => (
                    <div key={key} className="flex justify-between text-xs">
                      <span className="text-slate-400 font-mono">{key}:</span>
                      <span className="text-slate-200 font-mono">
                        {value === null || value === undefined ? "null" : value}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </TabsContent>

            {/* Stages Tab */}
            <TabsContent value="stages" className="mt-4">
              <div className="space-y-3 max-h-[400px] overflow-auto">
                {stages.length === 0 ? (
                  <div className="text-xs text-slate-400">No stages yet</div>
                ) : (
                  stages.map(stage => (
                    <details key={stage.stage} className="group" open>
                      <summary className="cursor-pointer text-xs font-mono text-slate-300 hover:text-white transition-colors list-none">
                        <span className="inline-flex items-center gap-2">
                          <ChevronDown className="w-3 h-3 transition-transform group-open:rotate-0 -rotate-90" />
                          <span className="font-semibold">{stage.stage}</span>
                          <span className="text-slate-500">({Object.keys(stage).length} keys)</span>
                        </span>
                      </summary>
                      <pre className="mt-2 ml-5 text-[10px] text-slate-300 overflow-auto bg-slate-950/50 p-2 rounded border border-slate-700/50">
                        {JSON.stringify(stage, null, 2)}
                      </pre>
                    </details>
                  ))
                )}
              </div>
            </TabsContent>

            {/* Timeline Tab */}
            <TabsContent value="timeline" className="mt-4">
              <div className="space-y-2 max-h-[400px] overflow-auto">
                {timeline.length === 0 ? (
                  <div className="text-xs text-slate-400">No timeline events yet</div>
                ) : (
                  timeline.map((event, idx) => (
                    <details key={event.id} className="group" open={idx === 0}>
                      <summary className="cursor-pointer text-xs font-mono text-slate-300 hover:text-white transition-colors list-none">
                        <span className="inline-flex items-center gap-2">
                          <ChevronDown className="w-3 h-3 transition-transform group-open:rotate-0 -rotate-90" />
                          <span className="text-slate-500">#{idx}</span>
                          <span className="font-semibold">{event.type}</span>
                          {event.stage && (
                            <span className="text-slate-500 text-[10px]">({event.stage})</span>
                          )}
                        </span>
                      </summary>
                      <pre className="mt-2 ml-5 text-[10px] text-slate-300 overflow-auto bg-slate-950/50 p-2 rounded border border-slate-700/50 max-h-[200px]">
                        {JSON.stringify(event, null, 2)}
                      </pre>
                    </details>
                  ))
                )}
              </div>
            </TabsContent>
          </Tabs>
        </div>
      )}
    </div>
  );
}
