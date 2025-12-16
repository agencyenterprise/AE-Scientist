"use client";

import { Activity, Cpu, FlaskConical, Package } from "lucide-react";
import type { StageProgress } from "@/types/research";
import { StatCard } from "./stat-card";

interface ResearchRunStatsProps {
  stageProgress: StageProgress[];
  gpuType: string | null;
  artifactsCount: number;
}

/**
 * Extract stage slug from backend stage name format
 * Example: "1_initial_implementation" → "initial_implementation"
 */
const extractStageSlug = (stageName: string): string => {
  const parts = stageName.split("_");
  const slugParts: string[] = [];
  for (let i = 1; i < parts.length; i++) {
    const part = parts[i];
    if (!part) continue;
    // Stop when we hit a number (substage number)
    if (/^\d+$/.test(part)) break;
    slugParts.push(part);
  }
  return slugParts.join("_");
};

const STAGE_ORDER = [
  "initial_implementation",
  "baseline_tuning",
  "creative_research",
  "ablation_studies",
  "paper_generation",
] as const;

/**
 * Calculate overall progress based on completed stages
 * Each stage = 20% (5 stages total)
 * Returns: (completedStages * 20)%
 */
function calculateOverallProgress(stageProgress: StageProgress[]): number {
  if (!stageProgress.length) return 0;

  // Map stage names to their latest progress
  const stageMap = new Map<string, StageProgress>();
  for (const sp of stageProgress) {
    const slug = extractStageSlug(sp.stage);
    if (slug) {
      stageMap.set(slug, sp);
    }
  }

  // Count completed stages (progress >= 1.0)
  let completedCount = 0;
  for (const slug of STAGE_ORDER) {
    const sp = stageMap.get(slug);
    if (!sp) break; // Haven't reached this stage yet
    if (sp.progress >= 1.0) {
      completedCount++;
    } else {
      break; // Current stage not complete, stop counting
    }
  }

  return completedCount * 20;
}

/**
 * Get display name for the current stage
 */
const getStageDisplayName = (stageProgress: StageProgress[]): string => {
  if (!stageProgress.length) return "Pending";
  const latestProgress = stageProgress[stageProgress.length - 1];
  return latestProgress?.stage || "Pending";
};

/**
 * Overview stats grid for research run detail page
 */
export function ResearchRunStats({
  stageProgress,
  gpuType,
  artifactsCount,
}: ResearchRunStatsProps) {
  const progressPercent = `${calculateOverallProgress(stageProgress)}%`;
  const currentStage = getStageDisplayName(stageProgress);

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      <StatCard
        icon={FlaskConical}
        iconColorClass="bg-emerald-500/15 text-emerald-400"
        label="Current Stage"
        value={currentStage}
        title={currentStage}
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
