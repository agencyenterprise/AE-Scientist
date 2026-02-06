"use client";

import { Activity, Cpu, FlaskConical, Package } from "lucide-react";
import { StatCard } from "./stat-card";
import { getCurrentStageLabel } from "../../utils/research-utils";

interface ResearchRunStatsProps {
  status: string;
  currentStage: string | null;
  progress: number | null;
  gpuType: string;
  artifactsCount: number;
}

/**
 * Overview stats grid for research run detail page
 */
export function ResearchRunStats({
  status,
  currentStage,
  progress,
  gpuType,
  artifactsCount,
}: ResearchRunStatsProps) {
  const currentStageLabel = getCurrentStageLabel(status, currentStage, progress);
  const progressLabel =
    progress === null || progress === undefined ? "-" : `${Math.round(progress * 100)}%`;

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      <StatCard
        icon={FlaskConical}
        iconColorClass="bg-emerald-500/15 text-emerald-400"
        label="Current Stage"
        value={currentStageLabel}
        title={currentStageLabel}
      />
      <StatCard
        icon={Activity}
        iconColorClass="bg-sky-500/15 text-sky-400"
        label="Progress"
        value={progressLabel}
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
