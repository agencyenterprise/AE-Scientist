"use client";

import { FlaskConical } from "lucide-react";

export function ResearchBoardEmpty() {
  return (
    <div className="flex h-64 items-center justify-center">
      <div className="text-center">
        <FlaskConical className="mx-auto mb-3 h-10 w-10 text-slate-600" />
        <h3 className="text-lg font-medium text-slate-300">No research runs found</h3>
        <p className="mt-1 text-sm text-slate-500">
          Start a research pipeline run from a conversation.
        </p>
      </div>
    </div>
  );
}
