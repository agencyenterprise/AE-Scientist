"use client";

import { useState } from "react";
import { useIsClient } from "@/shared/hooks/use-is-client";
import {
  getStageRelevantNodeTypes,
  NODE_TYPE_COLORS,
  BORDER_STYLES,
  NODE_TYPE_DESCRIPTIONS,
  BorderStyle,
} from "@/shared/lib/tree-colors";
import { Modal } from "@/shared/components/Modal";

interface Props {
  stageId?: string;
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
      <Modal isOpen={open} onClose={() => setOpen(false)} title="Node Types" maxWidth="max-w-md">
        <div className="space-y-6">
          {/* Node Types */}
          <div className="space-y-3 max-h-96 overflow-y-auto">
            {relevantNodeTypes.map(nodeType => {
              const config = NODE_TYPE_COLORS[nodeType];
              return (
                <div key={nodeType} className="flex gap-3 items-start">
                  <svg width="24" height="24" viewBox="0 0 24 24" className="flex-shrink-0 mt-0.5">
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
                    <div className="text-xs text-slate-400">{NODE_TYPE_DESCRIPTIONS[nodeType]}</div>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Node Status */}
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
        </div>
      </Modal>
    </>
  );
}
