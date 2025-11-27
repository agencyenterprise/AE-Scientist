import ReactMarkdown from "react-markdown";

import { markdownComponents } from "../utils/markdownComponents";

interface HypothesisSectionProps {
  content: string;
}

export function HypothesisSection({ content }: HypothesisSectionProps) {
  return (
    <div className="border-l-4 border-primary pl-4">
      <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-1">
        Hypothesis
      </h3>
      <div className="text-sm text-foreground leading-relaxed">
        <ReactMarkdown components={markdownComponents}>{content}</ReactMarkdown>
      </div>
    </div>
  );
}
