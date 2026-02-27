"use client";

import { Check, X, Zap, Crown } from "lucide-react";
import { cn } from "@/shared/lib/utils";

type Tier = "standard" | "premium";

interface TierSelectorProps {
  selectedTier: Tier;
  onTierChange: (tier: Tier) => void;
}

const FEATURE_LIST = [
  {
    label: "Structured feedback across multiple weakness categories",
    standard: true,
    premium: true,
  },
  { label: "Conference-specific scoring (NeurIPS, ICLR)", standard: true, premium: true },
  { label: "Web-grounded novelty assessment", standard: true, premium: true },
  { label: "Key citation verification", standard: true, premium: true },
  { label: "Missing key reference detection", standard: false, premium: true },
  {
    label: "Presentation quality analysis (figures, tables, formatting)",
    standard: false,
    premium: true,
  },
  { label: "Enhanced depth of analyses", standard: false, premium: true },
  { label: "Best accept/reject calibration", standard: false, premium: true },
] as const;

const CLAIMS: Record<Tier, string[]> = {
  standard: [
    "Identifies 17+ specific weaknesses per review",
    "2.6 actionability score vs 2.4 for human reviewers",
    "Catches ~70% of issues human reviewers identify",
  ],
  premium: [
    "85% agreement with human review panels (κ=0.71)",
    "19+ specific weaknesses per review",
  ],
};

const TIERS = [
  {
    id: "standard" as const,
    name: "Standard",
    icon: Zap,
    estimate: "~2 min",
    price: "from $0.23",
    borderColor: "border-amber-500/60",
    bgColor: "bg-amber-500/5",
    iconColor: "text-amber-400",
    ringColor: "ring-amber-500/30",
  },
  {
    id: "premium" as const,
    name: "Premium",
    icon: Crown,
    estimate: "~5 min",
    price: "from $3.45",
    borderColor: "border-sky-500/60",
    bgColor: "bg-sky-500/5",
    iconColor: "text-sky-400",
    ringColor: "ring-sky-500/30",
    badge: "Recommended",
  },
] as const;

export function TierSelector({ selectedTier, onTierChange }: TierSelectorProps) {
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {TIERS.map(tier => {
        const Icon = tier.icon;
        const isSelected = selectedTier === tier.id;
        return (
          <button
            key={tier.id}
            type="button"
            onClick={() => onTierChange(tier.id)}
            className={cn(
              "relative rounded-xl border p-4 text-left transition-all",
              isSelected
                ? `${tier.borderColor} ${tier.bgColor} ring-2 ${tier.ringColor}`
                : "border-slate-700/60 hover:border-slate-600"
            )}
          >
            {"badge" in tier && tier.badge && (
              <span className="absolute -top-2.5 right-3 rounded-full bg-sky-500 px-2 py-0.5 text-[10px] font-semibold text-white">
                {tier.badge}
              </span>
            )}

            <div className="flex items-center gap-2">
              <Icon className={cn("h-4 w-4", isSelected ? tier.iconColor : "text-slate-500")} />
              <span className="text-sm font-semibold text-white">{tier.name}</span>
            </div>

            <div className="mt-2 flex items-baseline gap-2">
              <span className="text-xs text-slate-400">{tier.price}</span>
              <span className="text-xs text-slate-500">{tier.estimate}</span>
            </div>

            <div className="mt-3 space-y-1">
              {CLAIMS[tier.id].map(claim => (
                <p key={claim} className="text-[11px] italic text-slate-400">
                  {claim}
                </p>
              ))}
            </div>

            <div className="mt-3 space-y-1">
              {FEATURE_LIST.map(feature => {
                const included = feature[tier.id];
                return (
                  <div key={feature.label} className="flex items-center gap-1.5">
                    {included ? (
                      <Check className="h-3 w-3 text-emerald-400" />
                    ) : (
                      <X className="h-3 w-3 text-slate-600" />
                    )}
                    <span className={cn("text-xs", included ? "text-slate-300" : "text-slate-600")}>
                      {feature.label}
                    </span>
                  </div>
                );
              })}
            </div>
          </button>
        );
      })}
    </div>
  );
}
