"use client";

import { AlertCircle } from "lucide-react";

interface ResearchRunErrorProps {
  message: string;
}

/**
 * Error message banner for research run failures
 */
export function ResearchRunError({ message }: ResearchRunErrorProps) {
  return (
    <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-4">
      <div className="flex items-start gap-3">
        <AlertCircle className="mt-0.5 h-5 w-5 flex-shrink-0 text-red-400" />
        <div>
          <h3 className="font-medium text-red-400">Error</h3>
          <p className="mt-1 text-sm text-red-300">{message}</p>
        </div>
      </div>
    </div>
  );
}
