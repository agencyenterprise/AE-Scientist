"use client";

import React from "react";
import { Loader2 } from "lucide-react";

export type ViewMode = "chat" | "split" | "project";

interface ViewModeTabsProps {
  viewMode: ViewMode;
  pendingView: ViewMode | null;
  onViewChange: (mode: ViewMode) => void;
}

const VIEW_MODE_CONFIG: Array<{ mode: ViewMode; label: string; title: string }> = [
  { mode: "chat", label: "Chat", title: "Show Imported Chat" },
  { mode: "split", label: "Split", title: "Split View" },
  { mode: "project", label: "Project", title: "Show Project Draft" },
];

export function ViewModeTabs({ viewMode, pendingView, onViewChange }: ViewModeTabsProps) {
  const isTransitioning = pendingView !== null && viewMode !== pendingView;

  return (
    <div className="hidden sm:flex view-tabs mr-2">
      {VIEW_MODE_CONFIG.map(({ mode, label, title }) => {
        const isActive = viewMode === mode;
        const isPending = pendingView === mode && viewMode !== mode;

        return (
          <button
            key={mode}
            type="button"
            onClick={() => onViewChange(mode)}
            disabled={isTransitioning}
            aria-busy={isPending}
            className={`view-tab ${isActive ? "view-tab-active" : "view-tab-inactive"}`}
            title={title}
          >
            {isPending ? (
              <div className="flex items-center gap-1">
                <Loader2 className="h-3 w-3 animate-spin" />
                <span>Loading</span>
              </div>
            ) : (
              label
            )}
          </button>
        );
      })}
    </div>
  );
}
