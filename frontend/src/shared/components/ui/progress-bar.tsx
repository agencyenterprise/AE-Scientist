"use client";

import { cn } from "@/shared/lib/utils";

export interface ProgressBarProps {
  progress: number | null;
  className?: string;
}

export function ProgressBar({ progress, className }: ProgressBarProps) {
  if (progress === null || progress === undefined) {
    return <span className="text-sm text-slate-500">No progress yet</span>;
  }

  const percentage = Math.round(progress * 100);

  return (
    <div className={cn("flex items-center gap-3", className)}>
      <div className="h-2 w-32 overflow-hidden rounded-full bg-slate-800">
        <div
          className="h-full rounded-full bg-emerald-500 transition-all duration-500"
          style={{ width: `${percentage}%` }}
        />
      </div>
      <span className="text-sm font-medium text-slate-300">{percentage}%</span>
    </div>
  );
}
