"use client";

import { ResearchBoardCardHeader } from "./research-board-card-header";
import { ResearchBoardCardBody } from "./research-board-card-body";
import { ResearchBoardCardFooter } from "./research-board-card-footer";

export interface ResearchBoardCardProps {
  runId: string;
  displayRunId: string;
  ideaTitle: string;
  ideaHypothesis: string | null;
  status: string;
  currentStage: string | null;
  progress: number | null;
  gpuType: string | null;
  createdByName: string;
  createdAt: string;
  artifactsCount: number;
  errorMessage: string | null;
}

export function ResearchBoardCard({
  runId,
  displayRunId,
  ideaTitle,
  ideaHypothesis,
  status,
  currentStage,
  progress,
  gpuType,
  createdByName,
  createdAt,
  artifactsCount,
  errorMessage,
}: ResearchBoardCardProps) {
  return (
    <div className="group rounded-xl border border-slate-800 bg-slate-900/50 transition-all hover:border-slate-700 hover:bg-slate-900/80">
      <ResearchBoardCardHeader displayRunId={displayRunId} status={status} />
      <ResearchBoardCardBody
        ideaTitle={ideaTitle}
        ideaHypothesis={ideaHypothesis}
        status={status}
        errorMessage={errorMessage}
        currentStage={currentStage}
        progress={progress}
        gpuType={gpuType}
      />
      <ResearchBoardCardFooter
        runId={runId}
        createdByName={createdByName}
        createdAt={createdAt}
        artifactsCount={artifactsCount}
      />
    </div>
  );
}
