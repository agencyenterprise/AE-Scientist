import ReactMarkdown from "react-markdown";

import { markdownComponents } from "../utils/markdownComponents";

interface RelatedWorkSectionProps {
  content: string;
}

export function RelatedWorkSection({ content }: RelatedWorkSectionProps) {
  return (
    <div>
      <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">
        Related Work
      </h3>
      <div className="text-sm text-foreground/90 leading-relaxed">
        <ReactMarkdown components={markdownComponents}>{content}</ReactMarkdown>
      </div>
    </div>
  );
}
