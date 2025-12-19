"use client";

import { useMemo, useState } from "react";
import type { TreeVizItem, ArtifactMetadata } from "@/types/research";
import { formatDateTime } from "@/shared/lib/date-utils";
import { TreeVizViewer } from "./tree-viz-viewer";

interface Props {
  treeViz?: TreeVizItem[] | null;
  conversationId: number | null;
  artifacts: ArtifactMetadata[];
}

const STAGE_SUMMARIES: Record<string, string> = {
  Stage_1:
    "Goal: Develop functional code which can produce a runnable result. The tree represents attempts and fixes needed to reach this state.",
  Stage_2:
    "Goal: Improve the baseline through tuning and small changes to the code while keeping the overall approach fixed. The scientist tries to improve the metrics which quantify the quality of the research.",
  Stage_3:
    "Goal: Explore higher-leverage variants and research directions, supported by plots and analyses to understand what is driving performance. The scientist tries to find and validate meaningful improvements worth writing up.",
  Stage_4:
    "Goal: Run controlled ablations and robustness checks to isolate which components matter and why. The scientist tries to attribute gains and strengthen the evidence for the final claims.",
};

function stageLabel(stageId: string): string {
  return stageId.replace("Stage_", "Stage ");
}

export function TreeVizCard({ treeViz, conversationId, artifacts }: Props) {
  const list = useMemo(() => treeViz ?? [], [treeViz]);
  const hasViz = list.length > 0 && conversationId !== null;

  // Track whether user has manually selected a stage (null = auto-follow mode)
  const [manuallySelectedStageId, setManuallySelectedStageId] = useState<string | null>(null);

  // Compute the most recent stage ID
  const mostRecentStageId = useMemo(() => {
    if (!hasViz) return null;
    const sortedByDate = [...list].sort(
      (a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
    );
    return sortedByDate[0]?.stage_id ?? null;
  }, [hasViz, list]);

  // Derived selected stage ID - uses manual selection if set, otherwise auto-follows most recent
  const selectedStageId = useMemo(() => {
    if (!hasViz) return null;

    // If user has manually selected a stage and it still exists, use it
    if (manuallySelectedStageId && list.find(v => v.stage_id === manuallySelectedStageId)) {
      return manuallySelectedStageId;
    }

    // Otherwise auto-follow the most recent stage
    return mostRecentStageId;
  }, [hasViz, list, manuallySelectedStageId, mostRecentStageId]);

  const selectedViz =
    hasViz && selectedStageId ? (list.find(v => v.stage_id === selectedStageId) ?? list[0]) : null;

  // Find best node for the selected stage using the is_best_node array in the tree viz payload
  const bestNodeForSelectedStage = useMemo(() => {
    if (!selectedViz) {
      return null;
    }

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const payload = selectedViz.viz as any;
    const isBestNodeArray = payload?.is_best_node;

    if (!isBestNodeArray || isBestNodeArray.length === 0) {
      return null;
    }

    // Find the index where is_best_node is true
    const bestNodeIndex = isBestNodeArray.findIndex((isBest: boolean) => isBest === true);

    return bestNodeIndex >= 0 ? bestNodeIndex : null;
  }, [selectedViz]);

  return (
    <div className="w-full rounded-lg border border-slate-800 bg-slate-900/60 p-4">
      <div className="mb-2 text-sm font-semibold text-slate-100">Tree Visualization</div>
      {!hasViz && <p className="text-sm text-slate-300">No tree visualization available yet.</p>}
      {hasViz && selectedViz && (
        <>
          <div className="mb-3 flex flex-wrap gap-2">
            {list.map(viz => (
              <button
                key={`${viz.stage_id}-${viz.id}`}
                type="button"
                onClick={() => {
                  setManuallySelectedStageId(viz.stage_id);
                }}
                className={`rounded px-3 py-1 text-xs ${
                  viz.stage_id === selectedStageId
                    ? "bg-emerald-500 text-slate-900"
                    : "bg-slate-800 text-slate-200 hover:bg-slate-700"
                }`}
              >
                {stageLabel(viz.stage_id)}
              </button>
            ))}
          </div>
          <p className="mb-2 text-xs text-slate-300">
            {STAGE_SUMMARIES[selectedViz.stage_id] ??
              "Explore and evaluate candidate solutions for this stage. The tree shows how the run iterates on ideas, tests changes, and selects better-performing nodes."}
          </p>
          <div className="mb-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-400">
            <span>
              <span className="text-slate-500">Start:</span>{" "}
              {formatDateTime(selectedViz.created_at)}
            </span>
            <span>
              <span className="text-slate-500">End:</span> {formatDateTime(selectedViz.updated_at)}
            </span>
          </div>
          <TreeVizViewer
            viz={selectedViz}
            artifacts={artifacts}
            bestNodeId={bestNodeForSelectedStage}
          />
        </>
      )}
    </div>
  );
}
