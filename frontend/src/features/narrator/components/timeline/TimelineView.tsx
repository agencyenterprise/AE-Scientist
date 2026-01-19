/**
 * TimelineView - Main timeline container with stage-grouped events.
 */

import { groupEventsByStage } from "@/features/narrator/lib/narratorSelectors";
import { ScrollArea } from "@/shared/components/ui/scroll-area";
import { createSubscription } from "@/shared/lib/subscription";
import type { components } from "@/types/api.gen";
import { forwardRef, useCallback, useImperativeHandle, useMemo, useRef } from "react";
import { isNearBottom } from "../../lib/scrollUtils";
import { StageSection } from "./StageSection";

type ResearchRunState = components["schemas"]["ResearchRunState"];

export interface TimelineViewHandle {
  scrollToEvent: (eventId: string) => boolean;
  scrollToBottom: (animated?: boolean) => void;
  getScrollContainer: () => HTMLElement | null;
  isNearBottom: (threshold?: number) => boolean;
  onScroll: (callback: (event: Event) => void) => () => void;
}

interface TimelineViewProps {
  state: ResearchRunState | null;
  isLoading?: boolean;
  onViewNode?: (nodeId: string) => void;
  expandedStages: string[];
  toggleExpanded: (stageId: string) => void;
  onEventFocus?: (eventId: string | null) => void;
  children?: React.ReactNode;
}

export const TimelineView = forwardRef<TimelineViewHandle, TimelineViewProps>(function TimelineView(
  { state, isLoading = false, onViewNode, expandedStages, toggleExpanded, onEventFocus, children },
  ref
) {
  const timelineContainer = useRef<HTMLDivElement>(null);
  const scrollSubscription = useRef(createSubscription<Event>());

  // Expose scroll control methods via ref
  useImperativeHandle(ref, () => {
    const api = {
      scrollToEvent: (eventId: string) => {
        const container = timelineContainer.current;
        if (!container) return false;
        const scrollContainer = container.parentElement;
        if (!scrollContainer) return false;

        const element = scrollContainer.querySelector(`[data-event-id="${eventId}"]`);
        if (!element) return false;

        // Calculate offset from sticky headers
        const stickyHeaders = scrollContainer.querySelectorAll("[data-sticky-header]");
        const stickyOffset = Array.from(stickyHeaders).reduce((total, header) => {
          return total + header.getBoundingClientRect().height;
        }, 0);

        const totalOffset = stickyOffset + 16; // Add breathing room

        const elementRect = element.getBoundingClientRect();
        const containerRect = scrollContainer.getBoundingClientRect();
        const relativeTop = elementRect.top - containerRect.top;
        const currentScroll = container.scrollTop;

        scrollContainer.scrollTo({
          top: Math.max(0, currentScroll + relativeTop - totalOffset),
          behavior: "smooth",
        });

        return true;
      },

      scrollToBottom: (animated = true) => {
        const container = timelineContainer.current;
        if (!container) return;
        const scrollContainer = container.parentElement;
        if (!scrollContainer) return;

        scrollContainer.scrollTo({
          top: scrollContainer.scrollHeight,
          behavior: animated ? "smooth" : "auto",
        });
      },

      getScrollContainer: () => timelineContainer.current?.parentElement || null,

      isNearBottom: (threshold: number = 150) => {
        const container = api.getScrollContainer();
        if (!container) return false;
        return isNearBottom(container, threshold);
      },

      onScroll: (callback: (event: Event) => void) => {
        return scrollSubscription.current.subscribe(callback);
      },
    };

    return api;
  }, []);

  // Group events by stage
  const stageGroups = useMemo(() => {
    return groupEventsByStage(state);
  }, [state]);

  // Determine which stages should be expanded by default
  const currentStage = state?.current_stage;

  const handleScroll = useCallback((event: Event) => {
    scrollSubscription.current.notify(event);
  }, []);

  const handleTimelineRef = useCallback(
    (el: HTMLDivElement | null) => {
      timelineContainer.current = el;
      const scrollingContainer = el?.parentElement;
      if (!scrollingContainer) {
        return;
      }

      let unsubscribe: () => void;
      if (scrollingContainer) {
        scrollingContainer.addEventListener("scroll", handleScroll);
        unsubscribe = () => scrollingContainer.removeEventListener("scroll", handleScroll);
      }

      return () => {
        if (unsubscribe) {
          unsubscribe();
        }
      };
    },
    [handleScroll]
  );

  if (!state || isLoading) {
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
    <ScrollArea
      className="h-[600px] border rounded-lg relative"
      scrollbarClassName="mx-1 mt-20 pb-24 w-4"
    >
      <div ref={handleTimelineRef} className="flex flex-col w-full pb-12">
        {stageGroups.map((stage, index) => {
          // Expand current stage and completed stages by default
          const defaultExpanded = stage.stageId === currentStage || stage.status === "completed";

          return (
            <StageSection
              isExpanded={expandedStages.includes(stage.stageId)}
              toggleExpanded={() => toggleExpanded(stage.stageId)}
              key={stage.stageId || `stage_${index}`}
              stage={stage}
              index={index}
              defaultExpanded={defaultExpanded}
              onViewNode={onViewNode}
              onEventFocus={onEventFocus}
            />
          );
        })}
      </div>
      {children}
    </ScrollArea>
  );
});
