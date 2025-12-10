"use client";

import { cn } from "@/shared/lib/utils";

interface ReviewTabsProps {
  activeTab: "both" | "scores" | "analysis";
  onTabChange: (tab: "both" | "scores" | "analysis") => void;
}

const TABS = [
  { id: "both", label: "Both" },
  { id: "scores", label: "Scores" },
  { id: "analysis", label: "Analysis" },
] as const;

/**
 * ReviewTabs Component
 *
 * Renders a tab navigation bar with three options:
 * - Both: Show both quantitative scores and qualitative analysis
 * - Scores: Show only quantitative scores
 * - Analysis: Show only qualitative analysis
 *
 * The active tab is highlighted with primary color styling.
 *
 * @param activeTab - Currently active tab: "both", "scores", or "analysis"
 * @param onTabChange - Callback when user clicks a tab
 */
export function ReviewTabs({ activeTab, onTabChange }: ReviewTabsProps) {
  return (
    <div className="flex border-b border-border mb-4">
      {TABS.map(tab => (
        <button
          key={tab.id}
          onClick={() => onTabChange(tab.id)}
          className={cn(
            "px-4 py-2 text-sm font-medium rounded-t transition",
            activeTab === tab.id
              ? "bg-primary text-primary-foreground border-b-2 border-primary -mb-px"
              : "bg-muted text-muted-foreground hover:bg-muted/80"
          )}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}
