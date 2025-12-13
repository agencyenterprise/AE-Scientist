"use client";

import { useState, useEffect } from "react";
import {
  AutoEvaluationCard,
  FinalPdfBanner,
  ResearchArtifactsList,
  ResearchLogsList,
  ResearchPipelineStages,
  ResearchRunDetailsGrid,
  ResearchRunError,
  ResearchRunHeader,
  ResearchRunStats,
  ReviewModal,
  CostDetailsCard,
  TreeVizCard,
} from "@/features/research/components/run-detail";
import { useResearchRunDetails } from "@/features/research/hooks/useResearchRunDetails";
import { useReviewData } from "@/features/research/hooks/useReviewData";
import { PageCard } from "@/shared/components/PageCard";
import { apiFetch } from "@/shared/lib/api-client";
import type { ResearchRunCostResponse } from "@/types";
import { AlertCircle, Loader2 } from "lucide-react";
import { useParams, useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";

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
    isConnected,
    connectionError,
    stopPending,
    stopError,
    handleStopRun,
    reconnect,
  } = useResearchRunDetails({ runId });

  const {
    review,
    loading: reviewLoading,
    error: reviewError,
    notFound,
    fetchReview,
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
    paper_generation_progress,
    best_node_selections = [],
  } = details;
  const canStopRun =
    conversationId !== null && (run.status === "running" || run.status === "pending");

  return (
    <PageCard>
      <div className="flex flex-col gap-6 p-6">
        <ResearchRunHeader
          runId={run.run_id}
          status={run.status}
          createdAt={run.created_at}
          isConnected={isConnected}
          connectionError={connectionError}
          canStopRun={canStopRun}
          stopPending={stopPending}
          stopError={stopError}
          onStopRun={handleStopRun}
          onReconnect={reconnect}
        />

        {run.error_message && <ResearchRunError message={run.error_message} />}

        {conversationId !== null && (
          <FinalPdfBanner artifacts={artifacts} conversationId={conversationId} runId={runId} />
        )}

        <ResearchRunStats
          stageProgress={stage_progress}
          gpuType={run.gpu_type}
          artifactsCount={artifacts.length}
        />

        <div className="flex flew-row gap-6">
          <div className="flex w-full sm:w-[60%]">
            <ResearchPipelineStages
              stageProgress={stage_progress}
              substageEvents={substage_events}
              paperGenerationProgress={paper_generation_progress}
              bestNodeSelections={best_node_selections ?? []}
              className="max-h-[600px] overflow-y-auto"
            />
          </div>
          <div className="flex flex-col w-full sm:w-[40%] max-h-[600px] overflow-y-auto">
            <ResearchRunDetailsGrid run={run} conversationId={conversationId} />

            <div className="mt-4">
              <CostDetailsCard cost={costDetails ?? null} isLoading={isLoadingCost} />
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
              artifacts={artifacts}
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
