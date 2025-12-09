"use client";

import { Lightbulb } from "lucide-react";
import type { IdeationQueueEmptyProps } from "../types/ideation-queue.types";

/**
 * Empty state component for the Ideation Queue
 * Displays appropriate message based on whether filters are active
 */
export function IdeationQueueEmpty({ hasFilters = false }: IdeationQueueEmptyProps) {
  return (
    <div className="flex h-64 items-center justify-center">
      <div className="text-center">
        <Lightbulb className="mx-auto mb-3 h-10 w-10 text-slate-600" />
        <h3 className="text-lg font-medium text-slate-300">
          {hasFilters ? "No ideas match your filters" : "No ideas yet"}
        </h3>
        <p className="mt-1 text-sm text-slate-500">
          {hasFilters
            ? "Try adjusting your search or filter criteria."
            : "Import conversations from Claude to start generating research ideas."}
        </p>
      </div>
    </div>
  );
}
