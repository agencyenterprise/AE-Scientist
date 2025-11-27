import ReactMarkdown from "react-markdown";

import { markdownComponents } from "../utils/markdownComponents";

interface ExpectedOutcomeSectionProps {
  content: string;
}

export function ExpectedOutcomeSection({ content }: ExpectedOutcomeSectionProps) {
  return (
    <div>
      <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">
        Expected Outcome
      </h3>
      <div className="text-sm text-foreground bg-green-500/10 border border-green-500/30 rounded-xl p-4 leading-relaxed">
        <ReactMarkdown components={markdownComponents}>{content}</ReactMarkdown>
      </div>
    </div>
  );
}
