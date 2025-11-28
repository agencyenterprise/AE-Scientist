import { ReactElement } from "react";
import ReactMarkdown from "react-markdown";
import { Pencil } from "lucide-react";

import { markdownComponents } from "../utils/markdownComponents";

interface AbstractSectionProps {
  content: string;
  diffContent?: ReactElement[] | null;
  onEdit?: () => void;
}

export function AbstractSection({ content, diffContent, onEdit }: AbstractSectionProps) {
  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
          Abstract
        </h3>
        {onEdit && (
          <button
            onClick={onEdit}
            className="p-1 text-muted-foreground hover:text-foreground hover:bg-muted rounded transition-colors"
            aria-label="Edit abstract"
          >
            <Pencil className="w-3.5 h-3.5" />
          </button>
        )}
      </div>
      <div className="text-sm text-foreground/90 leading-relaxed">
        {diffContent ? (
          <div className="whitespace-pre-wrap">{diffContent}</div>
        ) : (
          <ReactMarkdown components={markdownComponents}>{content}</ReactMarkdown>
        )}
      </div>
    </div>
  );
}
