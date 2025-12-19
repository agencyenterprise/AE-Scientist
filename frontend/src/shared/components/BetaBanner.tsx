"use client";

import { AlertCircle } from "lucide-react";

export function BetaBanner() {
  return (
    <div className="border-b border-amber-500/30 bg-amber-500/10 px-4 py-3">
      <div className="mx-auto max-w-7xl">
        <div className="flex items-start gap-3">
          <AlertCircle className="mt-0.5 h-5 w-5 flex-shrink-0 text-amber-400" />
          <div className="flex-1">
            <p className="text-sm font-semibold text-amber-200">
              AE Scientist is currently in Beta testing
            </p>
            <p className="mt-1 text-sm text-amber-100/90">
              Output quality and research completion reliability may be inconsistent. We&apos;d love to hear
              from you—{" "}
              <a
                href="mailto:james.bowler@ae.studio?subject=AE%20Scientist%20Feedback"
                className="font-semibold underline hover:text-amber-50 transition-colors"
              >
                send feedback
              </a>
              {" "}or report issues.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
