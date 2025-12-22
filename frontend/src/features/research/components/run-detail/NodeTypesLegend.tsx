"use client";

import { useState } from "react";
import { useIsClient } from "@/shared/hooks/use-is-client";
import { createPortal } from "react-dom";
import { X } from "lucide-react";
import {
  getStageRelevantNodeTypes,
  NODE_TYPE_COLORS,
  BORDER_STYLES,
  NODE_TYPE_DESCRIPTIONS,
  BorderStyle,
} from "@/shared/lib/tree-colors";

interface Props {
  stageId: string;
}

const CIRCLE_RADIUS = 8;

export function NodeTypesLegend({ stageId }: Props) {
  const isClient = useIsClient();
  const [open, setOpen] = useState(false);

  if (!isClient) return null;

  const relevantNodeTypes = getStageRelevantNodeTypes(stageId);
  const normalBorder = BORDER_STYLES[BorderStyle.Normal];
  const bestBorder = BORDER_STYLES[BorderStyle.Best];
  const failedBorder = BORDER_STYLES[BorderStyle.Failed];
  const selectedBorder = BORDER_STYLES[BorderStyle.Selected];

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        title="Show node type legend"
        className="inline-flex h-6 px-2 items-center justify-center rounded bg-slate-700 text-xs font-semibold text-slate-300 hover:bg-slate-600 transition-colors"
      >
        Legend
      </button>
      {open &&
        createPortal(
          <div className="fixed inset-0 z-[1000] flex items-center justify-center p-4 bg-black/50">
            <div className="relative rounded-lg border border-slate-700 bg-slate-800 p-6 shadow-xl max-w-md w-full">
              <button
                type="button"
                onClick={() => setOpen(false)}
                className="absolute top-4 right-4 p-1 hover:bg-slate-700 rounded transition-colors"
              >
                <X className="w-4 h-4 text-slate-400" />
              </button>
              <h2 className="text-lg font-semibold text-slate-100 mb-4">Node Types</h2>
              <div className="space-y-3 max-h-96 overflow-y-auto mb-6">
                {relevantNodeTypes.map(nodeType => {
                  const config = NODE_TYPE_COLORS[nodeType];
                  return (
                    <div key={nodeType} className="flex gap-3 items-start">
                      <svg
                        width="24"
                        height="24"
                        viewBox="0 0 24 24"
                        className="flex-shrink-0 mt-0.5"
                      >
                        <circle
                          cx="12"
                          cy="12"
                          r={CIRCLE_RADIUS}
                          fill={config.color}
                          stroke={normalBorder.stroke}
                          strokeWidth="2.2"
                        />
                      </svg>
                      <div className="flex-1">
                        <div className="font-semibold text-slate-100 text-sm">{config.label}</div>
                        <div className="text-xs text-slate-400">
                          {NODE_TYPE_DESCRIPTIONS[nodeType]}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>

              <div className="border-t border-slate-700 pt-4">
                <div className="text-xs font-semibold text-slate-300 mb-3">Node Status</div>
                <div className="space-y-2">
                  <div className="flex gap-3 items-center">
                    <svg width="24" height="24" viewBox="0 0 24 24" className="flex-shrink-0">
                      <circle
                        cx="12"
                        cy="12"
                        r={CIRCLE_RADIUS}
                        fill="#3B82F6"
                        stroke={bestBorder.stroke}
                        strokeWidth="2.2"
                      />
                    </svg>
                    <span className="text-xs text-slate-300">Best node</span>
                  </div>
                  <div className="flex gap-3 items-center">
                    <svg width="24" height="24" viewBox="0 0 24 24" className="flex-shrink-0">
                      <circle
                        cx="12"
                        cy="12"
                        r={CIRCLE_RADIUS}
                        fill="#3B82F6"
                        stroke={failedBorder.stroke}
                        strokeWidth="2.2"
                      />
                    </svg>
                    <span className="text-xs text-slate-300">Abandoned node</span>
                  </div>
                  <div className="flex gap-3 items-center">
                    <svg width="24" height="24" viewBox="0 0 24 24" className="flex-shrink-0">
                      <circle
                        cx="12"
                        cy="12"
                        r={CIRCLE_RADIUS}
                        fill="#3B82F6"
                        stroke={selectedBorder.stroke}
                        strokeWidth="2.2"
                      />
                    </svg>
                    <span className="text-xs text-slate-300">Selected node</span>
                  </div>
                </div>
              </div>

              <button
                type="button"
                onClick={() => setOpen(false)}
                className="mt-4 w-full rounded bg-slate-700 px-3 py-2 text-sm font-semibold text-slate-100 hover:bg-slate-600 transition-colors"
              >
                Close
              </button>
            </div>
          </div>,
          document.body
        )}
    </>
  );
}
