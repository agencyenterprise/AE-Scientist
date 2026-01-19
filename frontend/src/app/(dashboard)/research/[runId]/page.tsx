"use client";

import { useConversationResearchRuns } from "@/features/conversation/hooks/useConversationResearchRuns";
import {
  AutoEvaluationCard,
  CostDetailsCard,
  FinalPdfBanner,
  ImportSourceCard,
  ResearchArtifactsList,
  ResearchLogsList,
  ResearchPipelineStages,
  ResearchRunDetailsGrid,
  ResearchRunError,
  ResearchRunHeader,
  ResearchRunStats,
  ReviewModal,
  TreeVizCard,
} from "@/features/research/components/run-detail";
import { useResearchRunDetails } from "@/features/research/hooks/useResearchRunDetails";
import { useReviewData } from "@/features/research/hooks/useReviewData";
import { getCurrentStageAndProgress } from "@/features/research/utils/research-utils";
import { PageCard } from "@/shared/components/PageCard";
import { apiFetch } from "@/shared/lib/api-client";
import type { ResearchRunCostResponse } from "@/types";
import type { ResearchRunListItemApi } from "@/types/research";
import { useQuery } from "@tanstack/react-query";
import { AlertCircle, Loader2 } from "lucide-react";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

export default function ResearchRunDetailPage() {
  const params = useParams();
  const router = useRouter();
  const runId = params.runId as string;

  const [showReview, setShowReview] = useState(false);

  const {
    details,
    loading,
    error,
    conversationId,
    hwEstimatedCostCents,
    hwActualCostCents,
    hwCostPerHourCents,
    stopPending,
    stopError,
    handleStopRun,
    stageSkipState,
    skipPendingStage,
    handleSkipStage,
  } = useResearchRunDetails({
    runId,
    onReviewCompleted: newReview => setReview(newReview),
  });

  const { data: runMeta } = useQuery<ResearchRunListItemApi>({
    queryKey: ["researchRunMeta", runId],
    queryFn: () => apiFetch(`/research-runs/${runId}/`),
    enabled: !!runId,
    staleTime: 60 * 1000,
  });

  const { runs: conversationRuns } = useConversationResearchRuns(conversationId);

  const {
    review,
    loading: reviewLoading,
    error: reviewError,
    notFound,
    fetchReview,
    setReview,
  } = useReviewData({
    runId,
    conversationId,
  });

  const { data: costDetails, isLoading: isLoadingCost } = useQuery<ResearchRunCostResponse>({
    queryKey: ["researchRunCost", runId],
    queryFn: () => apiFetch(`/research-runs/${runId}/costs`),
    enabled: !!runId,
    refetchInterval: 10000,
  });

  // Auto-fetch evaluation data when conversationId is available
  useEffect(() => {
    if (conversationId !== null && !review && !notFound && !reviewError && !reviewLoading) {
      fetchReview();
    }
  }, [conversationId, review, notFound, reviewError, reviewLoading, fetchReview]);

  const handleTerminateExecution = useCallback(
    async (executionId: string, feedback: string) => {
      if (!conversationId) {
        throw new Error("Conversation not available yet. Please try again in a moment.");
      }
      await apiFetch(
        `/conversations/${conversationId}/idea/research-run/${runId}/executions/${executionId}/terminate`,
        {
          method: "POST",
          body: { payload: feedback },
        }
      );
    },
    [conversationId, runId]
  );

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-emerald-400" />
      </div>
    );
  }

  if (error || !details) {
    return (
      <div className="flex h-64 flex-col items-center justify-center gap-4">
        <AlertCircle className="h-12 w-12 text-red-400" />
        <p className="text-lg text-slate-300">{error || "Failed to load details"}</p>
        <button
          onClick={() => router.push("/research")}
          className="text-sm text-emerald-400 hover:text-emerald-300"
        >
          Back to Research Runs
        </button>
      </div>
    );
  }

  const {
    run,
    stage_progress,
    logs,
    artifacts,
    substage_events,
    substage_summaries = [],
    paper_generation_progress,
    best_node_selections = [],
    code_execution,
    code_executions,
  } = details;

  const codexExecution =
    code_executions?.codex_execution ??
    (code_execution?.run_type === "codex_execution" ? code_execution : null);
  const runfileExecution =
    code_executions?.runfile_execution ??
    (code_execution?.run_type === "runfile_execution" ? code_execution : null);
  const canStopRun =
    conversationId !== null && (run.status === "running" || run.status === "pending");

  const runNumber = (() => {
    if (!conversationId || !conversationRuns.length) return null;
    const ideaId = run.idea_id;
    const sameIdeaRuns = conversationRuns
      .filter(r => r.idea_id === ideaId)
      .slice()
      .sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime());
    const idx = sameIdeaRuns.findIndex(r => r.run_id === runId);
    return idx >= 0 ? idx + 1 : null;
  })();

  const title = runMeta?.idea_title?.trim() || "Untitled";

  // Compute current stage and progress from real-time SSE data
  // This replicates the backend's SQL logic and updates immediately without page refresh
  const { currentStage, progress: overallProgress } = getCurrentStageAndProgress(
    stage_progress,
    paper_generation_progress
  );

  return (
    <PageCard>
      <div className="flex flex-col gap-6 p-6">
        <ResearchRunHeader
          title={title}
          runNumber={runNumber}
          status={run.status}
          createdAt={run.created_at}
          canStopRun={canStopRun}
          stopPending={stopPending}
          stopError={stopError}
          onStopRun={handleStopRun}
        />

        {run.error_message && <ResearchRunError message={run.error_message} />}

        {runMeta?.conversation_url && (
          <ImportSourceCard conversationUrl={runMeta.conversation_url} />
        )}

        {conversationId !== null && (
          <FinalPdfBanner artifacts={artifacts} conversationId={conversationId} runId={runId} />
        )}

        <ResearchRunStats
          status={run.status}
          currentStage={currentStage}
          progress={overallProgress}
          gpuType={run.gpu_type}
          artifactsCount={artifacts.length}
        />

        <div className="flex flew-row gap-6">
          <div className="flex w-full sm:w-[60%]">
            <ResearchPipelineStages
              stageProgress={stage_progress}
              substageEvents={substage_events}
              substageSummaries={substage_summaries}
              paperGenerationProgress={paper_generation_progress}
              bestNodeSelections={best_node_selections ?? []}
              stageSkipState={stageSkipState}
              codexExecution={codexExecution}
              runfileExecution={runfileExecution}
              runStatus={run.status}
              onTerminateExecution={conversationId ? handleTerminateExecution : undefined}
              onSkipStage={conversationId ? handleSkipStage : undefined}
              skipPendingStage={skipPendingStage}
              className="max-h-[600px] overflow-y-auto"
            />
          </div>
          <div className="flex flex-col w-full sm:w-[40%] max-h-[600px] overflow-y-auto">
            <ResearchRunDetailsGrid run={run} conversationId={conversationId} />

            <div className="mt-4">
              <CostDetailsCard
                cost={costDetails ?? null}
                isLoading={isLoadingCost}
                hwEstimatedCostCents={hwEstimatedCostCents}
                hwCostPerHourCents={hwCostPerHourCents}
                hwActualCostCents={hwActualCostCents}
              />
            </div>

            {/* Auto Evaluation Card */}
            <div className="mt-4">
              <AutoEvaluationCard
                review={review}
                loading={reviewLoading}
                notFound={notFound}
                error={reviewError}
                disabled={conversationId === null}
                onViewDetails={() => setShowReview(true)}
              />
            </div>
          </div>
        </div>

        <div className="flex flex-row items-stretch gap-6">
          <div className="flex w-full sm:w-[60%] max-h-[600px] overflow-y-auto">
            <ResearchLogsList logs={logs} />
          </div>
          <div className="flex w-full sm:w-[40%] max-h-[600px] overflow-y-auto flex-col gap-4">
            {conversationId !== null ? (
              <ResearchArtifactsList
                artifacts={artifacts}
                conversationId={conversationId}
                runId={runId}
              />
            ) : (
              <p className="text-sm text-slate-400">Conversation not yet available.</p>
            )}
          </div>
        </div>

        {conversationId !== null && (
          <div className="w-full">
            <TreeVizCard
              treeViz={details.tree_viz ?? []}
              conversationId={conversationId}
              runId={runId}
              artifacts={artifacts}
              substageSummaries={substage_summaries}
            />
          </div>
        )}
      </div>

      {showReview && (
        <ReviewModal
          review={review}
          notFound={notFound}
          error={reviewError}
          onClose={() => setShowReview(false)}
          loading={reviewLoading}
        />
      )}
    </PageCard>
  );
}
