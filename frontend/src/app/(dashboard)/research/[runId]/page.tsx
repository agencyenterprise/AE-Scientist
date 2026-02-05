"use client";

import { useConversationResearchRuns } from "@/features/conversation/hooks/useConversationResearchRuns";
import {
  ResearchRunHeader,
  ResearchSummaryStrip,
  OverviewTab,
  TreeTab,
  ArtifactsTab,
  LogsTab,
  EvaluationTab,
  RunCostTab,
} from "@/features/research/components/run-detail";
import { useResearchRunDetails } from "@/features/research/hooks/useResearchRunDetails";
import { useReviewData } from "@/features/research/hooks/useReviewData";
import { getCurrentStageAndProgress } from "@/features/research/utils/research-utils";
import { PageCard } from "@/shared/components/PageCard";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/shared/components/ui/tabs";
import { api } from "@/shared/lib/api-client-typed";
import type { ResearchRunCostResponse } from "@/types";
import type { ResearchRunListItemApi } from "@/types/research";
import { useQuery } from "@tanstack/react-query";
import {
  AlertCircle,
  GitBranch,
  Layers,
  Loader2,
  Package,
  ScrollText,
  ShieldCheck,
  DollarSign,
} from "lucide-react";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

export default function ResearchRunDetailPage() {
  const params = useParams();
  const router = useRouter();
  const runId = params.runId as string;

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
    seedPending,
    seedError,
    handleSeedNewIdea,
  } = useResearchRunDetails({
    runId,
    onReviewCompleted: newReview => setReview(newReview),
  });

  const { data: runMeta } = useQuery<ResearchRunListItemApi>({
    queryKey: ["researchRunMeta", runId],
    queryFn: async () => {
      const { data } = await api.GET("/api/research-runs/{run_id}/", {
        params: { path: { run_id: runId } },
      });
      return data as unknown as ResearchRunListItemApi;
    },
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
    queryFn: async () => {
      const { data } = await api.GET("/api/research-runs/{run_id}/costs", {
        params: { path: { run_id: runId } },
      });
      return data as ResearchRunCostResponse;
    },
    enabled: !!runId,
    refetchInterval: 10000,
  });

  useEffect(() => {
    if (conversationId !== null && !review && !notFound && !reviewError && !reviewLoading) {
      fetchReview();
    }
  }, [conversationId, review, notFound, reviewError, reviewLoading, fetchReview]);

  const [activeTab, setActiveTab] = useState("overview");

  const handleTerminateExecution = useCallback(
    async (executionId: string, feedback: string) => {
      if (!conversationId) {
        throw new Error("Conversation not available yet. Please try again in a moment.");
      }
      const { error } = await api.POST(
        "/api/conversations/{conversation_id}/idea/research-run/{run_id}/executions/{execution_id}/terminate",
        {
          params: {
            path: {
              conversation_id: conversationId,
              run_id: runId,
              execution_id: executionId,
            },
          },
          body: { payload: feedback },
        }
      );
      if (error) throw new Error("Failed to terminate execution");
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
    substage_summaries = [],
    paper_generation_progress,
  } = details;
  const canStopRun =
    conversationId !== null &&
    (run.status === "running" || run.status === "initializing" || run.status === "pending");

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

  const { currentStage, progress: overallProgress } = getCurrentStageAndProgress(
    stage_progress,
    paper_generation_progress
  );

  const hwCostUsd =
    hwActualCostCents !== null
      ? hwActualCostCents / 100
      : hwEstimatedCostCents !== null
        ? hwEstimatedCostCents / 100
        : null;
  const modelCostUsd = costDetails?.total_cost ?? null;
  const totalCostUsd =
    hwCostUsd !== null || modelCostUsd !== null ? (hwCostUsd ?? 0) + (modelCostUsd ?? 0) : null;

  return (
    <PageCard>
      <div className="flex flex-col gap-6 p-6">
        <ResearchRunHeader
          title={title}
          runNumber={runNumber}
          status={run.status}
          terminationStatus={run.termination_status}
          createdAt={run.created_at}
          canStopRun={canStopRun}
          stopPending={stopPending}
          stopError={stopError}
          onStopRun={handleStopRun}
          conversationId={conversationId}
          onSeedNewIdea={handleSeedNewIdea}
          seedPending={seedPending}
          seedError={seedError}
        />

        <ResearchSummaryStrip
          status={run.status}
          currentStage={currentStage}
          progress={overallProgress}
          review={review}
          reviewLoading={reviewLoading}
          totalCost={totalCostUsd}
          isEstimatedCost={hwActualCostCents === null && hwEstimatedCostCents !== null}
          createdAt={run.created_at}
          updatedAt={run.updated_at}
        />

        <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
          <TabsList className="mb-6 h-auto w-full justify-start gap-1 rounded-lg border border-border bg-muted/50 p-1">
            <TabsTrigger value="overview" className="gap-1.5 data-[state=active]:bg-background">
              <Layers className="h-3.5 w-3.5" />
              <span className="hidden sm:inline">Overview</span>
            </TabsTrigger>
            <TabsTrigger value="stages" className="gap-1.5 data-[state=active]:bg-background">
              <GitBranch className="h-3.5 w-3.5" />
              <span className="hidden sm:inline">Research Tree</span>
            </TabsTrigger>
            <TabsTrigger value="artifacts" className="gap-1.5 data-[state=active]:bg-background">
              <Package className="h-3.5 w-3.5" />
              <span className="hidden sm:inline">Artifacts</span>
              <span className="rounded-full bg-muted px-1.5 py-0.5 text-[10px] font-medium">
                {artifacts.length}
              </span>
            </TabsTrigger>
            <TabsTrigger value="logs" className="gap-1.5 data-[state=active]:bg-background">
              <ScrollText className="h-3.5 w-3.5" />
              <span className="hidden sm:inline">Logs</span>
              <span className="rounded-full bg-muted px-1.5 py-0.5 text-[10px] font-medium">
                {logs.length}
              </span>
            </TabsTrigger>
            <TabsTrigger value="evaluation" className="gap-1.5 data-[state=active]:bg-background">
              <ShieldCheck className="h-3.5 w-3.5" />
              <span className="hidden sm:inline">Evaluation</span>
            </TabsTrigger>
            <TabsTrigger value="runcost" className="gap-1.5 data-[state=active]:bg-background">
              <DollarSign className="h-3.5 w-3.5" />
              <span className="hidden sm:inline">Run & Cost</span>
            </TabsTrigger>
          </TabsList>

          <TabsContent value="overview">
            <OverviewTab
              run={run}
              conversationId={conversationId}
              runId={runId}
              conversationUrl={
                runMeta?.conversation_id ? `/conversations/${runMeta.conversation_id}` : null
              }
              artifacts={artifacts}
              review={review}
              reviewLoading={reviewLoading}
              onViewEvaluation={() => setActiveTab("evaluation")}
              onTerminateExecution={conversationId ? handleTerminateExecution : undefined}
            />
          </TabsContent>

          <TabsContent value="stages">
            <TreeTab
              treeViz={details.tree_viz ?? []}
              conversationId={conversationId}
              runId={runId}
              artifacts={artifacts}
              substageSummaries={substage_summaries}
            />
          </TabsContent>

          <TabsContent value="artifacts">
            <ArtifactsTab artifacts={artifacts} conversationId={conversationId} runId={runId} />
          </TabsContent>

          <TabsContent value="logs">
            <LogsTab logs={logs} />
          </TabsContent>

          <TabsContent value="evaluation">
            <EvaluationTab
              review={review}
              reviewLoading={reviewLoading}
              reviewNotFound={notFound}
              reviewError={reviewError}
              conversationId={conversationId}
            />
          </TabsContent>

          <TabsContent value="runcost">
            <RunCostTab
              run={run}
              conversationId={conversationId}
              costDetails={costDetails ?? null}
              isLoadingCost={isLoadingCost}
              hwEstimatedCostCents={hwEstimatedCostCents}
              hwCostPerHourCents={hwCostPerHourCents}
              hwActualCostCents={hwActualCostCents}
            />
          </TabsContent>
        </Tabs>
      </div>
    </PageCard>
  );
}
