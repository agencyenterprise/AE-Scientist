import ReactMarkdown from "react-markdown";
import { AlertTriangle } from "lucide-react";

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
              <AlertTriangle className="w-5 h-5 text-amber-400 flex-shrink-0 mt-0.5" />
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
