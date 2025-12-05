"use client";

import {
  FinalPdfBanner,
  ResearchArtifactsList,
  ResearchLogsList,
  ResearchPipelineStages,
  ResearchRunDetailsGrid,
  ResearchRunError,
  ResearchRunHeader,
  ResearchRunStats,
} from "@/features/research/components/run-detail";
import { useResearchRunDetails } from "@/features/research/hooks/useResearchRunDetails";
import { PageCard } from "@/shared/components/PageCard";
import { AlertCircle, Loader2 } from "lucide-react";
import { useParams, useRouter } from "next/navigation";

export default function ResearchRunDetailPage() {
  const params = useParams();
  const router = useRouter();
  const runId = params.runId as string;

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

  const { run, stage_progress, logs, artifacts, experiment_nodes } = details;
  const latestProgress = stage_progress[stage_progress.length - 1];
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
          latestProgress={latestProgress}
          gpuType={run.gpu_type}
          artifactsCount={artifacts.length}
        />

        <div className="flex flew-row gap-6">
          <div className="flex w-full sm:w-[60%] max-h-[600px] overflow-y-auto">
            <ResearchPipelineStages
              stageProgress={stage_progress}
              experimentNodes={experiment_nodes}
            />
          </div>
          <div className="flex w-full sm:w-[40%] max-h-[600px] overflow-y-auto">
            <ResearchRunDetailsGrid run={run} conversationId={conversationId} />

            {/*Validation Summary*/}
          </div>
        </div>

        <div className="flex flex-row items-stretch gap-6">
          <div className="flex w-full sm:w-[60%] max-h-[600px] overflow-y-auto">
            <ResearchLogsList logs={logs} />
          </div>
          <div className="flex w-full sm:w-[40%] max-h-[600px] overflow-y-auto">
            {conversationId !== null && (
              <ResearchArtifactsList
                artifacts={artifacts}
                conversationId={conversationId}
                runId={runId}
              />
            )}
          </div>
        </div>
      </div>
    </PageCard>
  );
}
