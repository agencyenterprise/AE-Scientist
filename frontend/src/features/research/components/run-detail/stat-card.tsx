"use client";

import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

interface StatCardProps {
  icon: LucideIcon;
  iconColorClass: string;
  label: string;
  value: ReactNode;
  title?: string;
}

/**
 * Reusable stat card for the research run overview grid
 */
export function StatCard({ icon: Icon, iconColorClass, label, value, title }: StatCardProps) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-4">
      <div className="flex items-start gap-3">
        <div
          className={`flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-lg ${iconColorClass}`}
        >
          <Icon className="h-5 w-5" />
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-xs text-slate-400">{label}</p>
          <p className="break-words font-medium text-white" title={title}>
            {value}
          </p>
        </div>
      </div>
    </div>
  );
}
