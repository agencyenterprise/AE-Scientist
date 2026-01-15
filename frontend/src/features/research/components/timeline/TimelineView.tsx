/**
 * TimelineView - Main timeline container with stage-grouped events.
 */

import { useMemo } from "react";
import type { components } from "@/types/api.gen";
import { groupEventsByStage } from "@/features/research/lib/narratorSelectors";
import { StageSection } from "./StageSection";
import { Skeleton } from "@/shared/components/ui/skeleton";
import { ScrollArea } from "@/shared/components/ui/scroll-area";

type ResearchRunState = components["schemas"]["ResearchRunState"];

interface TimelineViewProps {
  state: ResearchRunState | null;
  isLoading?: boolean;
  onViewNode?: (nodeId: string) => void;
  expandedStages: string[];
  toggleExpanded: (stageId: string) => void;
}

export function TimelineView({
  state,
  isLoading = false,
  onViewNode,
  expandedStages,
  toggleExpanded,
}: TimelineViewProps) {
  // Group events by stage
  const stageGroups = useMemo(() => {
    return groupEventsByStage(state);
  }, [state]);

  // Determine which stages should be expanded by default
  const currentStage = state?.current_stage;

  if (isLoading) {
    return <TimelineLoadingSkeleton />;
  }

  if (!state) {
    return (
      <div className="text-center py-12 text-slate-400">
        <p className="text-lg font-semibold mb-2">No timeline data</p>
        <p className="text-sm">Waiting for research run to start...</p>
      </div>
    );
  }

  if (stageGroups.length === 0) {
    return (
      <div className="text-center py-12 text-slate-400">
        <p className="text-lg font-semibold mb-2">No stages yet</p>
        <p className="text-sm">Timeline will appear as the research progresses.</p>
      </div>
    );
  }

  return (
    <ScrollArea className="h-[600px] border rounded-lg" scrollbarClassName="mx-1 mt-20 pb-24 w-4">
      <div className="flex flex-col gap-2 w-full">
        {stageGroups.map((stage, index) => {
          // Expand current stage and completed stages by default
          const defaultExpanded = stage.stageId === currentStage || stage.status === "completed";

          return (
            <StageSection
              // note: when status changes, this component should be remounted
              // to ensure it auto-expands when new events arrive
              // key={`${stage.stageId}-${stage.status}`}
              isExpanded={expandedStages.includes(stage.stageId)}
              toggleExpanded={() => toggleExpanded(stage.stageId)}
              key={`${stage.stageId}`}
              stage={stage}
              index={index}
              defaultExpanded={defaultExpanded}
              onViewNode={onViewNode}
            />
          );
        })}
      </div>
    </ScrollArea>
  );
}

/**
 * Loading skeleton for timeline.
 */
function TimelineLoadingSkeleton() {
  return (
    <div className="space-y-4">
      {[1, 2, 3].map(i => (
        <div key={i} className="border border-slate-700/50 rounded-lg overflow-hidden">
          {/* Header skeleton */}
          <div className="px-4 py-3 bg-slate-900/95">
            <div className="flex items-center justify-between gap-4">
              <div className="flex-1 space-y-2">
                <Skeleton className="h-5 w-48 bg-slate-800/50" />
                <Skeleton className="h-3 w-32 bg-slate-800/50" />
              </div>
              <Skeleton className="h-8 w-24 bg-slate-800/50" />
            </div>
          </div>

          {/* Content skeleton */}
          <div className="p-4 space-y-3 bg-slate-900/30">
            <Skeleton className="h-24 w-full bg-slate-800/50" />
            <Skeleton className="h-24 w-full bg-slate-800/50" />
          </div>
        </div>
      ))}
    </div>
  );
}
