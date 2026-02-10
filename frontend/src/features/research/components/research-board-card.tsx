"use client";

import { ResearchBoardCardHeader } from "./research-board-card-header";
import { ResearchBoardCardBody } from "./research-board-card-body";
import { ResearchBoardCardFooter } from "./research-board-card-footer";

export interface ResearchBoardCardProps {
  runId: string;
  displayRunId: string;
  ideaTitle: string;
  ideaMarkdown: string | null; // Full idea content in markdown format
  status: string;
  currentStage: string | null;
  progress: number | null;
  gpuType: string;
  createdByName: string;
  createdAt: string;
  artifactsCount: number;
  errorMessage: string | null;
  parentRunId: string | null;
  evaluationOverall: number | null;
  evaluationDecision: string | null;
}

export function ResearchBoardCard({
  runId,
  displayRunId,
  ideaTitle,
  ideaMarkdown,
  status,
  currentStage,
  progress,
  gpuType,
  createdByName,
  createdAt,
  artifactsCount,
  errorMessage,
  parentRunId,
  evaluationOverall,
  evaluationDecision,
}: ResearchBoardCardProps) {
  return (
    <div className="group rounded-2xl border border-slate-800 bg-slate-900/50 transition-all hover:border-slate-700 hover:bg-slate-900/80">
      <ResearchBoardCardHeader
        displayRunId={displayRunId}
        status={status}
        parentRunId={parentRunId}
      />
      <ResearchBoardCardBody
        ideaTitle={ideaTitle}
        ideaMarkdown={ideaMarkdown}
        status={status}
        errorMessage={errorMessage}
        currentStage={currentStage}
        progress={progress}
        gpuType={gpuType}
        evaluationOverall={evaluationOverall}
        evaluationDecision={evaluationDecision}
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
