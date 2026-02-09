"use client";

import type { ModelCost, ResearchRunCostResponse } from "@/types";
import { DollarSign, Loader2, Zap, Server, HelpCircle } from "lucide-react";
import { Tooltip, TooltipTrigger, TooltipContent } from "@/shared/components/ui/tooltip";

interface CostDetailsCardProps {
  cost: ResearchRunCostResponse | null;
  isLoading: boolean;
  hwEstimatedCostCents: number | null;
  hwCostPerHourCents: number | null;
  hwActualCostCents: number | null;
}

// Helper to shorten model names for display while keeping full name in tooltip
function formatModelName(modelName: string): { short: string; full: string } {
  const full = modelName;
  // Common patterns to shorten
  const shortPatterns: [RegExp, string][] = [
    [/^claude-3-5-sonnet-\d+$/, "Claude 3.5 Sonnet"],
    [/^claude-3-opus-\d+$/, "Claude 3 Opus"],
    [/^claude-3-haiku-\d+$/, "Claude 3 Haiku"],
    [/^gpt-4-turbo.*$/, "GPT-4 Turbo"],
    [/^gpt-4o.*$/, "GPT-4o"],
    [/^gpt-4.*$/, "GPT-4"],
    [/^gpt-3\.5-turbo.*$/, "GPT-3.5 Turbo"],
    [/^gemini-1\.5-pro.*$/, "Gemini 1.5 Pro"],
    [/^gemini-1\.5-flash.*$/, "Gemini 1.5 Flash"],
    [/^o1-preview.*$/, "o1 Preview"],
    [/^o1-mini.*$/, "o1 Mini"],
    [/^deepseek.*$/, "DeepSeek"],
  ];

  for (const [pattern, short] of shortPatterns) {
    if (pattern.test(modelName)) {
      return { short, full };
    }
  }

  // If no pattern matches and name is long, truncate intelligently
  if (modelName.length > 24) {
    return { short: modelName.slice(0, 20) + "…", full };
  }

  return { short: modelName, full };
}

export function CostDetailsCard({
  cost,
  isLoading,
  hwEstimatedCostCents,
  hwCostPerHourCents,
  hwActualCostCents,
}: CostDetailsCardProps) {
  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(amount);
  };

  const hwEstimatedUsd =
    typeof hwEstimatedCostCents === "number" ? hwEstimatedCostCents / 100 : null;
  const hwRateUsdPerHour = typeof hwCostPerHourCents === "number" ? hwCostPerHourCents / 100 : null;
  const hwActualUsd = typeof hwActualCostCents === "number" ? hwActualCostCents / 100 : null;
  const hwCostUsd = hwActualUsd ?? hwEstimatedUsd;
  const hasActualHwCost = hwActualUsd !== null;
  const totalCostWithHw = cost ? cost.total_cost + (hwCostUsd ?? 0) : null;
  const totalIsEstimated = hwActualUsd === null && hwEstimatedUsd !== null;

  // Calculate model cost total for summary
  const modelCostTotal = cost?.cost_by_model.reduce((acc, m) => acc + m.cost, 0) ?? 0;

  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900/50 w-full p-4 sm:p-6 overflow-hidden">
      <div className="mb-4 flex items-center gap-2">
        <DollarSign className="h-5 w-5 text-emerald-400 flex-shrink-0" />
        <h2 className="text-lg font-semibold text-white">Cost Details</h2>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center h-24">
          <Loader2 className="h-8 w-8 animate-spin text-emerald-400" />
        </div>
      ) : cost ? (
        <div className="space-y-6">
          {/* Total Cost - Highlighted */}
          <div className="bg-slate-800/50 rounded-lg p-4 border border-emerald-500/20">
            <div className="flex items-center justify-between flex-wrap gap-2">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium text-slate-300">
                  {totalIsEstimated ? "Total Cost (estimated)" : "Total Cost"}
                </span>
              </div>
              <span className="font-mono text-2xl font-bold text-emerald-400">
                {totalCostWithHw !== null
                  ? formatCurrency(totalCostWithHw)
                  : formatCurrency(cost.total_cost)}
              </span>
            </div>
          </div>

          {/* Cost Breakdown Grid */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {/* Hardware Costs */}
            <div className="space-y-3">
              <div className="flex items-center gap-2 text-sm font-medium text-slate-400 border-b border-slate-700 pb-2">
                <Server className="h-4 w-4 flex-shrink-0" />
                <span>Hardware</span>
              </div>

              <div className="space-y-2">
                <div className="flex justify-between items-center">
                  <span className="text-xs text-slate-400">Actual</span>
                  <span className="font-mono text-sm text-white">
                    {hwActualCostCents !== null ? formatCurrency(hwActualCostCents / 100) : "—"}
                  </span>
                </div>

                <div className="flex justify-between items-center">
                  <div className="flex items-center gap-1">
                    <span className="text-xs text-slate-400">Estimated</span>
                    {hwRateUsdPerHour !== null && (
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <button type="button" className="text-slate-500 hover:text-slate-400">
                            <HelpCircle className="h-3 w-3" />
                          </button>
                        </TooltipTrigger>
                        <TooltipContent
                          side="top"
                          className="bg-slate-800 text-slate-200 border-slate-700"
                        >
                          Rate: {formatCurrency(hwRateUsdPerHour)}/hour
                        </TooltipContent>
                      </Tooltip>
                    )}
                  </div>
                  <span
                    className={`font-mono text-white ${hasActualHwCost ? "text-xs line-through text-slate-500" : "text-sm"}`}
                  >
                    {hwEstimatedUsd !== null ? formatCurrency(hwEstimatedUsd) : "—"}
                  </span>
                </div>
              </div>
            </div>

            {/* Model Costs */}
            <div className="space-y-3">
              <div className="flex items-center justify-between gap-2 text-sm font-medium text-slate-400 border-b border-slate-700 pb-2">
                <div className="flex items-center gap-2">
                  <Zap className="h-4 w-4 flex-shrink-0" />
                  <span>AI Models</span>
                </div>
                <span className="font-mono text-xs text-emerald-400">
                  {formatCurrency(modelCostTotal)}
                </span>
              </div>

              <div className="space-y-2 max-h-40 overflow-y-auto pr-1">
                {cost.cost_by_model.length > 0 ? (
                  cost.cost_by_model.map((modelCost: ModelCost) => {
                    const { short, full } = formatModelName(modelCost.model);
                    const needsTooltip = short !== full;

                    return (
                      <div
                        key={modelCost.model}
                        className="flex justify-between items-center gap-2"
                      >
                        {needsTooltip ? (
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <span className="text-xs text-slate-400 truncate cursor-help">
                                {short}
                              </span>
                            </TooltipTrigger>
                            <TooltipContent
                              side="left"
                              className="bg-slate-800 text-slate-200 border-slate-700 font-mono text-xs"
                            >
                              {full}
                            </TooltipContent>
                          </Tooltip>
                        ) : (
                          <span className="text-xs text-slate-400 truncate">{short}</span>
                        )}
                        <span className="font-mono text-sm text-white flex-shrink-0">
                          {formatCurrency(modelCost.cost)}
                        </span>
                      </div>
                    );
                  })
                ) : (
                  <p className="text-xs text-slate-500">No model costs recorded</p>
                )}
              </div>
            </div>
          </div>
        </div>
      ) : (
        <p className="text-sm text-center text-slate-400">Could not load cost details.</p>
      )}
    </div>
  );
}
