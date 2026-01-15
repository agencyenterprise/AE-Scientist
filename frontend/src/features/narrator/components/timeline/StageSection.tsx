/**
 * StageSection - Collapsible section for a stage with its timeline events.
 */

import { useMemo } from "react";
import { motion, AnimatePresence } from "motion/react";
import type { StageGroup } from "@/features/narrator/lib/narratorSelectors";
import { groupSimilarEvents } from "@/features/narrator/lib/eventGrouping";
import { StageHeader } from "./StageHeader";
import { EventCard } from "./EventCard";
import { EventGroup } from "./EventGroup";

interface StageSectionProps {
  stage: StageGroup;
  index: number;
  defaultExpanded?: boolean;
  onViewNode?: (nodeId: string) => void;
  onEventFocus?: (eventId: string | null) => void;
  isExpanded: boolean;
  toggleExpanded: () => void;
}

export function StageSection({
  stage,
  index,
  isExpanded,
  toggleExpanded,
  onViewNode,
  onEventFocus,
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

      {/* Collapsible content with animation */}
      <AnimatePresence initial={false}>
        {isExpanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2, ease: "easeInOut" }}
            className="overflow-hidden"
          >
            <div className="border-slate-700/50 rounded-b-lg pl-3 pr-6 pt-3 pb-3 space-y-3 bg-slate-900/30">
              {eventItems.length === 0 ? (
                <div className="text-center py-8 text-slate-400 text-sm">
                  No events yet for this stage.
                </div>
              ) : (
                <AnimatePresence mode="popLayout">
                  {eventItems.map((item, idx) => {
                    if (item.type === "single") {
                      return (
                        <motion.div
                          key={item.event.id || idx}
                          initial={{ opacity: 0, y: 20 }}
                          animate={{ opacity: 1, y: 0 }}
                          exit={{ opacity: 0, y: -20 }}
                          transition={{ duration: 0.3, ease: "easeOut" }}
                          layout
                        >
                          <EventCard
                            event={item.event}
                            onViewNode={onViewNode}
                            onEventFocus={onEventFocus}
                          />
                        </motion.div>
                      );
                    } else {
                      return (
                        <motion.div
                          key={item.latestEvent.id || idx}
                          initial={{ opacity: 0, y: 20 }}
                          animate={{ opacity: 1, y: 0 }}
                          exit={{ opacity: 0, y: -20 }}
                          transition={{ duration: 0.3, ease: "easeOut" }}
                          layout
                        >
                          <EventGroup
                            events={item.events}
                            count={item.count}
                            onViewNode={onViewNode}
                            onEventFocus={onEventFocus}
                          />
                        </motion.div>
                      );
                    }
                  })}
                </AnimatePresence>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
