/**
 * StageSection - Collapsible section for a stage with its timeline events.
 */

import { useState, useMemo } from "react";
import type { StageGroup } from "@/features/research/lib/narratorSelectors";
import { groupSimilarEvents } from "@/features/research/lib/eventGrouping";
import { StageHeader } from "./StageHeader";
import { EventCard } from "./EventCard";
import { EventGroup } from "./EventGroup";

interface StageSectionProps {
  stage: StageGroup;
  index: number;
  defaultExpanded?: boolean;
  onViewNode?: (nodeId: string) => void;
  isExpanded: boolean;
  toggleExpanded: () => void;
}

export function StageSection({
  stage,
  index,
  isExpanded,
  toggleExpanded,
  onViewNode,
}: StageSectionProps) {
  // Group similar events using our pure function
  const eventItems = useMemo(() => {
    return groupSimilarEvents(stage.events);
  }, [stage.events]);

  return (
    <div>
      {/* Sticky header - positioned relative to scroll container */}
      <div className="sticky top-0 z-10">
        <StageHeader
          stage={stage}
          stageIndex={index}
          isExpanded={isExpanded}
          onToggle={toggleExpanded}
        />
      </div>

      {/* Collapsible content */}
      {isExpanded && (
        <div className="border-slate-700/50 rounded-b-lg pl-3 pr-6 pt-3 pb-3 space-y-3 bg-slate-900/30">
          {eventItems.length === 0 ? (
            <div className="text-center py-8 text-slate-400 text-sm">
              No events yet for this stage.
            </div>
          ) : (
            eventItems.map((item, idx) => {
              if (item.type === "single") {
                return (
                  <EventCard
                    key={item.event.id || idx}
                    event={item.event}
                    onViewNode={onViewNode}
                  />
                );
              } else {
                return (
                  <EventGroup
                    key={item.latestEvent.id || idx}
                    events={item.events}
                    count={item.count}
                    onViewNode={onViewNode}
                  />
                );
              }
            })
          )}
        </div>
      )}
    </div>
  );
}
