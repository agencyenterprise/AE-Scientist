import { ReactElement } from "react";
import ReactMarkdown from "react-markdown";
import { AlertTriangle, Pencil, Plus, Trash2 } from "lucide-react";

import { markdownComponents } from "../utils/markdownComponents";

interface RiskFactorsSectionProps {
  risks: string[];
  diffContent?: (ReactElement[] | null)[];
  deletedItems?: ReactElement[][];
  onEditAll?: () => void;
  onEditItem?: (index: number) => void;
  onAddItem?: () => void;
  onDeleteItem?: (index: number) => void;
  isDeleting?: boolean;
}

export function RiskFactorsSection({
  risks,
  diffContent,
  deletedItems,
  onEditAll,
  onEditItem,
  onAddItem,
  onDeleteItem,
  isDeleting = false,
}: RiskFactorsSectionProps) {
  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
          Risk Factors & Limitations
        </h3>
        <div className="flex items-center gap-1">
          {onAddItem && (
            <button
              onClick={onAddItem}
              disabled={isDeleting}
              className="p-1 text-muted-foreground hover:text-amber-400 hover:bg-amber-500/10 rounded transition-colors disabled:opacity-50"
              aria-label="Add risk factor"
              title="Add new risk factor"
            >
              <Plus className="w-3.5 h-3.5" />
            </button>
          )}
          {onEditAll && (
            <button
              onClick={onEditAll}
              className="p-1 text-muted-foreground hover:text-foreground hover:bg-muted rounded transition-colors"
              aria-label="Edit all risk factors"
            >
              <Pencil className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>
      <div className="space-y-2">
        {risks.map((risk, idx) => {
          const itemDiff = diffContent?.[idx];
          return (
            <div
              key={idx}
              className="group bg-amber-500/10 border border-amber-500/30 rounded-xl p-4"
            >
              <div className="flex items-start gap-3">
                <AlertTriangle className="w-5 h-5 text-amber-400 flex-shrink-0 mt-0.5" />
                <div className="flex-1 text-sm text-foreground leading-relaxed">
                  {itemDiff ? (
                    <div className="whitespace-pre-wrap">{itemDiff}</div>
                  ) : (
                    <ReactMarkdown components={markdownComponents}>{risk}</ReactMarkdown>
                  )}
                </div>
                <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                  {onEditItem && (
                    <button
                      onClick={() => onEditItem(idx)}
                      className="p-1 text-muted-foreground hover:text-foreground hover:bg-muted rounded transition-colors"
                      aria-label={`Edit risk factor ${idx + 1}`}
                    >
                      <Pencil className="w-3.5 h-3.5" />
                    </button>
                  )}
                  {onDeleteItem && risks.length > 1 && (
                    <button
                      onClick={() => onDeleteItem(idx)}
                      disabled={isDeleting}
                      className="p-1 text-muted-foreground hover:text-destructive hover:bg-destructive/10 rounded transition-colors disabled:opacity-50"
                      aria-label={`Delete risk factor ${idx + 1}`}
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  )}
                </div>
              </div>
            </div>
          );
        })}

        {/* Show deleted items */}
        {deletedItems?.map((deletedDiff, idx) => (
          <div
            key={`deleted-${idx}`}
            className="bg-red-500/10 border border-red-500/30 rounded-xl p-4 opacity-60"
          >
            <div className="flex items-start gap-3">
              <AlertTriangle className="w-5 h-5 text-red-400 flex-shrink-0 mt-0.5" />
              <div className="flex-1 text-sm text-foreground leading-relaxed">
                <div className="whitespace-pre-wrap">{deletedDiff}</div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
