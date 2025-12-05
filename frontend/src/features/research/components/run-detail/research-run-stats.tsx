"use client";

import { Activity, Cpu, FlaskConical, Package } from "lucide-react";
import type { StageProgress } from "@/types/research";
import { StatCard } from "./stat-card";

interface ResearchRunStatsProps {
  latestProgress: StageProgress | undefined;
  gpuType: string | null;
  artifactsCount: number;
}

/**
 * Overview stats grid for research run detail page
 */
export function ResearchRunStats({
  latestProgress,
  gpuType,
  artifactsCount,
}: ResearchRunStatsProps) {
  const progressPercent = latestProgress ? `${Math.round(latestProgress.progress * 100)}%` : "-";

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      <StatCard
        icon={FlaskConical}
        iconColorClass="bg-emerald-500/15 text-emerald-400"
        label="Current Stage"
        value={latestProgress?.stage || "Pending"}
        title={latestProgress?.stage || "Pending"}
      />
      <StatCard
        icon={Activity}
        iconColorClass="bg-sky-500/15 text-sky-400"
        label="Progress"
        value={progressPercent}
      />
      <StatCard
        icon={Cpu}
        iconColorClass="bg-purple-500/15 text-purple-400"
        label="GPU Type"
        value={gpuType || "-"}
      />
      <StatCard
        icon={Package}
        iconColorClass="bg-amber-500/15 text-amber-400"
        label="Artifacts"
        value={artifactsCount}
      />
    </div>
  );
}
