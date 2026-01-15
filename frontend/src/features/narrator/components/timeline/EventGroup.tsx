/**
 * EventGroup - Displays a group of similar consecutive events with carousel navigation.
 * Always shows carousel, defaults to newest event, allows browsing history.
 */

import type { components } from "@/types/api.gen";
import { EventCard } from "./EventCard";
import { Card, CardContent } from "@/shared/components/ui/card";
import {
  Carousel,
  CarouselContent,
  CarouselItem,
  CarouselNext,
  CarouselPrevious,
  type CarouselApi,
} from "@/shared/components/ui/carousel";
import { useEffect, useState } from "react";
import { ChevronsRight } from "lucide-react";
import { Button } from "@/shared/components/ui/button";

type ResearchRunState = components["schemas"]["ResearchRunState"];
type TimelineEvent = NonNullable<ResearchRunState["timeline"]>[number];

interface EventGroupProps {
  events: TimelineEvent[];
  count: number;
  onViewNode?: (nodeId: string) => void;
  onEventFocus?: (eventId: string | null) => void;
}

export function EventGroup({ events, count, onViewNode, onEventFocus }: EventGroupProps) {
  const [api, setApi] = useState<CarouselApi>();
  const [current, setCurrent] = useState(0);
  const [isAtEnd, setIsAtEnd] = useState(true);

  // Update current slide when carousel changes
  useEffect(() => {
    if (!api) return;

    const updateState = () => {
      setCurrent(api.selectedScrollSnap());
      setIsAtEnd(!api.canScrollNext());
    };

    updateState();
    api.on("select", updateState);

    return () => {
      api.off("select", updateState);
    };
  }, [api]);

  // Auto-scroll to newest event when events array changes (new event arrives)
  useEffect(() => {
    if (api && events.length > 0) {
      // Scroll to last slide (newest event)
      api.scrollTo(events.length - 1, false);
    }
  }, [api, events.length]);

  const scrollToNewest = () => {
    if (api) {
      api.scrollTo(events.length - 1, false); // true = animated
    }
  };

  return (
    <div className="relative">
      {/* Stack indicator - visual depth effect with subtle animation */}
      <div className="absolute -top-1 -right-1 -left-1 h-full bg-slate-800/30 rounded-lg -z-10 transition-all duration-200" />
      <div className="absolute -top-2 -right-2 -left-2 h-full bg-slate-800/15 rounded-lg -z-20 transition-all duration-200" />

      <Card className="border-slate-700/80 relative p-1">
        <CardContent className="p-0">
          {/* Carousel - always visible */}
          <div className="relative">
            <Carousel
              setApi={setApi}
              opts={{
                align: "center",
                loop: false,
                startIndex: events.length - 1, // Start at newest
              }}
              className="w-full"
            >
              <CarouselContent className="pt-2 pb-3">
                {events.map((event, idx) => (
                  <CarouselItem key={event.id || idx}>
                    <div className="px-8 select-none">
                      <EventCard
                        event={event}
                        compact
                        onViewNode={onViewNode}
                        onEventFocus={onEventFocus}
                      />
                    </div>
                  </CarouselItem>
                ))}
              </CarouselContent>
              <CarouselPrevious className="-left-1 h-8 w-8" />
              <CarouselNext className="-right-1 h-8 w-8" />
              {/* Count badge */}
              {!isAtEnd && (
                <div className="absolute -bottom-3 right-3 bg-blue-500 text-white text-xs font-semibold px-2.5 py-1 rounded-full shadow-lg z-10">
                  {/* Show "back to newest" button when not at end */}
                  <div className="flex items-center gap-1">
                    <Button
                      variant="ghost"
                      size="xs"
                      onClick={scrollToNewest}
                      className="h-6 text-xs text-white"
                    >
                      <ChevronsRight className="w-3 h-3 mr-1" />
                      Jump to newest
                    </Button>
                  </div>
                </div>
              )}
            </Carousel>
          </div>

          {/* Footer with position indicator and "back to newest" button */}
          <div className="py-1 border-t border-slate-700/50 flex items-center justify-between">
            <span className="text-xs text-slate-400">
              Event {current + 1} of {count}
              {isAtEnd && <span className="ml-2 text-emerald-400">• Latest</span>}
            </span>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
