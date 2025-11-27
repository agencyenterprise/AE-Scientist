import ReactMarkdown from "react-markdown";

import { markdownComponents } from "../utils/markdownComponents";

interface RiskFactorsSectionProps {
  risks: string[];
}

export function RiskFactorsSection({ risks }: RiskFactorsSectionProps) {
  return (
    <div>
      <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">
        Risk Factors & Limitations
      </h3>
      <div className="space-y-2">
        {risks.map((risk, idx) => (
          <div key={idx} className="bg-amber-500/10 border border-amber-500/30 rounded-xl p-4">
            <div className="flex items-start gap-3">
              <svg
                className="w-5 h-5 text-amber-400 flex-shrink-0 mt-0.5"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
                />
              </svg>
              <div className="flex-1 text-sm text-foreground leading-relaxed">
                <ReactMarkdown components={markdownComponents}>{risk}</ReactMarkdown>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
