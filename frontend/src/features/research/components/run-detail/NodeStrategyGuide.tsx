"use client";

import { useEffect, useState } from "react";
import { useIsClient } from "@/shared/hooks/use-is-client";
import { createPortal } from "react-dom";
import { X, ChevronDown } from "lucide-react";
import { getStageStrategy } from "@/shared/lib/node-strategy-data";

interface Props {
  stageId: string;
}

export function NodeStrategyGuide({ stageId }: Props) {
  const isClient = useIsClient();
  const [open, setOpen] = useState(false);
  const [expandedPhases, setExpandedPhases] = useState<Set<string>>(new Set());

  useEffect(() => {
    if (!open) return;

    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setOpen(false);
      }
    };

    document.addEventListener("keydown", handleEscape);
    return () => document.removeEventListener("keydown", handleEscape);
  }, [open]);

  if (!isClient) return null;

  const strategy = getStageStrategy(stageId);
  if (!strategy) return null;

  const togglePhase = (phaseName: string) => {
    const newExpanded = new Set(expandedPhases);
    if (newExpanded.has(phaseName)) {
      newExpanded.delete(phaseName);
    } else {
      newExpanded.add(phaseName);
    }
    setExpandedPhases(newExpanded);
  };

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        title="Show node selection strategy"
        className="inline-flex h-6 px-2 items-center justify-center rounded bg-slate-700 text-xs font-semibold text-slate-300 hover:bg-slate-600 transition-colors"
      >
        Node Strategy
      </button>
      {open &&
        createPortal(
          <div className="fixed inset-0 z-[1000] flex items-center justify-center p-4 bg-black/50">
            <div className="relative rounded-lg border border-slate-700 bg-slate-800 p-6 shadow-xl max-w-2xl w-full max-h-96 overflow-y-auto">
              <button
                type="button"
                onClick={() => setOpen(false)}
                className="absolute top-4 right-4 p-1 hover:bg-slate-700 rounded transition-colors flex-shrink-0"
              >
                <X className="w-4 h-4 text-slate-400" />
              </button>

              <div className="pr-6">
                {/* Header */}
                <h2 className="text-lg font-semibold text-slate-100 mb-1">{strategy.title}</h2>
                <p className="text-sm text-slate-400 mb-4">{strategy.goal}</p>

                {/* Description */}
                <p className="text-xs text-slate-300 mb-4 leading-relaxed">
                  {strategy.description}
                </p>

                {/* Overview */}
                <div className="mb-4 p-3 bg-slate-700/50 rounded border border-slate-600">
                  <h3 className="text-xs font-semibold text-slate-200 mb-2">
                    Decision Strategy Overview
                  </h3>
                  <p className="text-xs text-slate-300 leading-relaxed">
                    {strategy.nodeSelectionStrategy.overview}
                  </p>
                </div>

                {/* Phases */}
                {strategy.nodeSelectionStrategy.phases.length > 0 && (
                  <div className="mb-4">
                    <h3 className="text-xs font-semibold text-slate-300 mb-3">Selection Phases</h3>
                    <div className="space-y-2">
                      {strategy.nodeSelectionStrategy.phases.map((phase, idx) => {
                        const isExpanded = expandedPhases.has(phase.name);
                        return (
                          <div
                            key={idx}
                            className="border border-slate-600 rounded bg-slate-700/30"
                          >
                            <button
                              type="button"
                              onClick={() => togglePhase(phase.name)}
                              className="w-full flex items-center justify-between p-3 hover:bg-slate-700/50 transition-colors"
                            >
                              <div className="text-left">
                                <div className="text-xs font-semibold text-slate-200">
                                  {phase.name}
                                </div>
                                <div className="text-xs text-slate-400 mt-1">
                                  Trigger: {phase.trigger}
                                </div>
                              </div>
                              <ChevronDown
                                className={`w-4 h-4 text-slate-400 flex-shrink-0 ml-2 transition-transform ${
                                  isExpanded ? "rotate-180" : ""
                                }`}
                              />
                            </button>

                            {isExpanded && (
                              <div className="px-3 pt-3 pb-3 border-t border-slate-600 space-y-3">
                                {/* Description */}
                                <div>
                                  <p className="text-xs text-slate-300 leading-relaxed">
                                    {phase.description}
                                  </p>
                                </div>

                                {/* Action */}
                                <div>
                                  <div className="text-xs font-semibold text-slate-300 mb-1">
                                    Action:
                                  </div>
                                  <div className="text-xs text-slate-400 ml-2">{phase.action}</div>
                                </div>

                                {/* Config Values */}
                                {phase.configValues.length > 0 && (
                                  <div>
                                    <div className="text-xs font-semibold text-slate-300 mb-1">
                                      Config Values:
                                    </div>
                                    <div className="space-y-1">
                                      {phase.configValues.map((value, cidx) => (
                                        <div
                                          key={cidx}
                                          className="text-xs text-slate-300 ml-2 font-mono bg-slate-900/50 px-2 py-1 rounded border border-slate-600"
                                        >
                                          {value}
                                        </div>
                                      ))}
                                    </div>
                                  </div>
                                )}

                                {/* Selection Criteria */}
                                <div>
                                  <div className="text-xs font-semibold text-slate-300 mb-1">
                                    Selection Criteria:
                                  </div>
                                  <ul className="space-y-1 ml-2">
                                    {phase.selectionCriteria.map((criterion, cidx) => (
                                      <li key={cidx} className="text-xs text-slate-400">
                                        • {criterion}
                                      </li>
                                    ))}
                                  </ul>
                                </div>
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}

                {/* Example Flow */}
                <div className="mb-4 p-3 bg-slate-700/50 rounded border border-slate-600">
                  <h3 className="text-xs font-semibold text-slate-200 mb-2">
                    Example Decision Flow
                  </h3>
                  <pre className="text-xs text-slate-300 leading-relaxed whitespace-pre-wrap break-words">
                    {strategy.exampleFlow}
                  </pre>
                </div>
              </div>

              {/* Close button */}
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
