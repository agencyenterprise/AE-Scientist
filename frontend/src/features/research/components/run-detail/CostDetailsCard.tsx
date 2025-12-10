"use client";

import type { ModelCost, ResearchRunCostResponse } from "@/types";
import { DollarSign, Loader2 } from "lucide-react";
import React from "react";

interface CostDetailsCardProps {
  cost: ResearchRunCostResponse | null;
  isLoading: boolean;
}

export function CostDetailsCard({ cost, isLoading }: CostDetailsCardProps) {
  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(amount);
  };

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
            <dd className="font-mono text-lg text-white">{formatCurrency(cost.total_cost)}</dd>
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
