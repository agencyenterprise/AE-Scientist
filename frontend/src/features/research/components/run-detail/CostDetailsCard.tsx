"use client";

import type { ModelCost, ResearchRunCostResponse } from "@/types";
import { DollarSign, Loader2 } from "lucide-react";

interface CostDetailsCardProps {
  cost: ResearchRunCostResponse | null;
  isLoading: boolean;
  hwEstimatedCostCents: number | null;
  hwCostPerHourCents: number | null;
  hwActualCostCents: number | null;
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

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/50 w-full p-6">
      <div className="mb-4 flex items-center gap-2">
        <DollarSign className="h-5 w-5 text-slate-400" />
        <h2 className="text-lg font-semibold text-white">Cost Details</h2>
      </div>
      {isLoading ? (
        <div className="flex items-center justify-center h-24">
          <Loader2 className="h-8 w-8 animate-spin text-emerald-400" />
        </div>
      ) : cost ? (
        <dl className="grid gap-4 sm:grid-cols-2">
          <div className="sm:col-span-2">
            <dt className="text-xs text-slate-400">Total Cost</dt>
            <dd className="font-mono text-lg text-white">
              {totalCostWithHw !== null
                ? `${formatCurrency(totalCostWithHw)}${totalIsEstimated ? " (estimated)" : ""}`
                : formatCurrency(cost.total_cost)}
            </dd>
          </div>
          <div className="sm:col-span-2">
            <dt className="text-xs text-slate-400">HW actual cost</dt>
            <dd className="font-mono text-sm text-white">
              {hwActualCostCents !== null ? formatCurrency(hwActualCostCents / 100) : "—"}
            </dd>
          </div>
          <div className="sm:col-span-2">
            <dt className="text-xs text-slate-400">HW estimated cost</dt>
            <dd className={`font-mono text-white ${hasActualHwCost ? "text-xs" : "text-sm"}`}>
              {hwEstimatedUsd !== null
                ? `${formatCurrency(hwEstimatedUsd)}${
                    hwRateUsdPerHour !== null ? ` (${formatCurrency(hwRateUsdPerHour)}/hr)` : ""
                  }`
                : "—"}
            </dd>
          </div>
          {cost.cost_by_model.map((modelCost: ModelCost) => (
            <div key={modelCost.model}>
              <dt className="text-xs text-slate-400">Cost for {modelCost.model}</dt>
              <dd className="font-mono text-sm text-white">{formatCurrency(modelCost.cost)}</dd>
            </div>
          ))}
        </dl>
      ) : (
        <p className="text-sm text-center text-slate-400">Could not load cost details.</p>
      )}
    </div>
  );
}
