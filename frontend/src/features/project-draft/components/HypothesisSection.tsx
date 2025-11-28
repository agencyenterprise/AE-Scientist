import { ReactElement } from "react";
import ReactMarkdown from "react-markdown";
import { Pencil } from "lucide-react";

import { markdownComponents } from "../utils/markdownComponents";

interface HypothesisSectionProps {
  content: string;
  diffContent?: ReactElement[] | null;
  onEdit?: () => void;
}

export function HypothesisSection({ content, diffContent, onEdit }: HypothesisSectionProps) {
  return (
    <div className="border-l-4 border-primary pl-4">
      <div className="flex items-center justify-between mb-1">
        <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
          Hypothesis
        </h3>
        {onEdit && (
          <button
            onClick={onEdit}
            className="p-1 text-muted-foreground hover:text-foreground hover:bg-muted rounded transition-colors"
            aria-label="Edit hypothesis"
          >
            <Pencil className="w-3.5 h-3.5" />
          </button>
        )}
      </div>
      <div className="text-sm text-foreground leading-relaxed">
        {diffContent ? (
          <div className="whitespace-pre-wrap">{diffContent}</div>
        ) : (
          <ReactMarkdown components={markdownComponents}>{content}</ReactMarkdown>
        )}
      </div>
    </div>
  );
}
