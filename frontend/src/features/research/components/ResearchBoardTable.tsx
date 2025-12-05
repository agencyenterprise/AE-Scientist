"use client";

import { useMemo } from "react";
import type { ResearchRun } from "@/shared/lib/api-adapters";
import { formatRelativeTime } from "@/shared/lib/date-utils";
import { truncateRunId } from "../utils/research-utils";
import { ResearchBoardCard } from "./research-board-card";
import { ResearchBoardEmpty } from "./research-board-empty";

interface ResearchBoardTableProps {
  researchRuns: ResearchRun[];
}

export function ResearchBoardTable({ researchRuns }: ResearchBoardTableProps) {
  const cards = useMemo(() => {
    return researchRuns.map(run => ({
      runId: run.runId,
      displayRunId: truncateRunId(run.runId),
      ideaTitle: run.ideaTitle || "Untitled",
      ideaHypothesis: run.ideaHypothesis,
      status: run.status,
      currentStage: run.currentStage,
      progress: run.progress,
      gpuType: run.gpuType,
      createdByName: run.createdByName,
      createdAt: formatRelativeTime(run.createdAt),
      artifactsCount: run.artifactsCount,
      errorMessage: run.errorMessage,
    }));
  }, [researchRuns]);

  if (cards.length === 0) {
    return <ResearchBoardEmpty />;
  }

  return (
    <div className="grid gap-4">
      {cards.map(card => (
        <ResearchBoardCard key={card.runId} {...card} />
      ))}
    </div>
  );
}
