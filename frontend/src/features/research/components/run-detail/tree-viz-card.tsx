"use client";

import { useMemo, useState } from "react";
import type { TreeVizItem, ArtifactMetadata, SubstageSummary } from "@/types/research";
import { formatDateTime } from "@/shared/lib/date-utils";
import { TreeVizViewer } from "./tree-viz-viewer";
import { mergeTreeVizItems } from "@/shared/lib/tree-merge-utils";

interface Props {
  treeViz?: TreeVizItem[] | null;
  conversationId: number | null;
  artifacts: ArtifactMetadata[];
  substageSummaries?: SubstageSummary[];
}

const FULL_TREE_ID = "Full_Tree";

const STAGE_SUMMARIES: Record<string, string> = {
  Stage_1:
    "Goal: Develop functional code which can produce a runnable result. The tree represents attempts and fixes needed to reach this state.",
  Stage_2:
    "Goal: Improve the baseline through tuning and small changes to the code while keeping the overall approach fixed. The scientist tries to improve the metrics which quantify the quality of the research.",
  Stage_3:
    "Goal: Explore higher-leverage variants and research directions, supported by plots and analyses to understand what is driving performance. The scientist tries to find and validate meaningful improvements worth writing up.",
  Stage_4:
    "Goal: Run controlled ablations and robustness checks to isolate which components matter and why. The scientist tries to attribute gains and strengthen the evidence for the final claims.",
  [FULL_TREE_ID]:
    "Combined view showing all stages of the research pipeline stacked vertically in chronological order.",
};

function stageLabel(stageId: string): string {
  return stageId.replace("Stage_", "Stage ");
}

const STAGE_ID_TO_STAGE_KEY: Record<string, string> = {
  Stage_1: "initial_implementation",
  Stage_2: "baseline_tuning",
  Stage_3: "creative_research",
  Stage_4: "ablation_studies",
};

/**
 * Backend format: {stage_number}_{stage_slug}[_{substage_number}_{substage_slug}...]
 * Examples:
 *  - "1_initial_implementation" → "initial_implementation"
 *  - "2_baseline_tuning_2_optimization" → "baseline_tuning"
 */
function extractStageSlug(stageName: string): string | null {
  const parts = stageName.split("_");
  if (parts.length < 2) return null;

  const slugParts: string[] = [];
  for (let i = 1; i < parts.length; i++) {
    const part = parts[i];
    if (!part) continue;
    if (/^\d+$/.test(part)) break;
    slugParts.push(part);
  }

  return slugParts.length > 0 ? slugParts.join("_") : null;
}

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);

function getSummaryText(summary: SubstageSummary): string {
  if (!isRecord(summary.summary)) {
    return JSON.stringify(summary.summary, null, 2);
  }
  const llmSummary = summary.summary.llm_summary;
  if (typeof llmSummary === "string" && llmSummary.trim().length > 0) {
    return llmSummary.trim();
  }
  return JSON.stringify(summary.summary, null, 2);
}

export function TreeVizCard({ treeViz, conversationId, artifacts, substageSummaries }: Props) {
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

    // If user has manually selected Full Tree or a stage that still exists, use it
    if (manuallySelectedStageId) {
      if (manuallySelectedStageId === FULL_TREE_ID) {
        return FULL_TREE_ID;
      }
      if (list.find(v => v.stage_id === manuallySelectedStageId)) {
        return manuallySelectedStageId;
      }
    }

    // Otherwise auto-follow the most recent stage
    return mostRecentStageId;
  }, [hasViz, list, manuallySelectedStageId, mostRecentStageId]);

  // Create merged viz for Full Tree view
  const mergedViz = useMemo(() => {
    if (!hasViz || list.length === 0) return null;
    return mergeTreeVizItems(list);
  }, [hasViz, list]);

  const selectedViz = useMemo(() => {
    if (!hasViz || !selectedStageId) return null;
    if (selectedStageId === FULL_TREE_ID) return mergedViz;
    return list.find(v => v.stage_id === selectedStageId) ?? list[0];
  }, [hasViz, selectedStageId, list, mergedViz]);

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

  const stageSummaryText = useMemo(() => {
    if (!selectedViz) return null;
    if (!substageSummaries || substageSummaries.length === 0) return null;
    if (selectedViz.stage_id === FULL_TREE_ID) return null;

    const stageKey = STAGE_ID_TO_STAGE_KEY[selectedViz.stage_id];
    if (!stageKey) return null;

    const matches = substageSummaries.filter(summary => extractStageSlug(summary.stage) === stageKey);
    if (matches.length === 0) return null;

    const latest =
      matches.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())[0] ??
      null;
    if (!latest) return null;

    return getSummaryText(latest);
  }, [selectedViz, substageSummaries]);

  return (
    <div className="w-full rounded-lg border border-slate-800 bg-slate-900/60 p-4">
      <div className="mb-2">
        <span className="text-sm font-semibold text-slate-100">Tree Visualization</span>
      </div>
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
            <button
              key="full-tree"
              type="button"
              onClick={() => {
                setManuallySelectedStageId(FULL_TREE_ID);
              }}
              className={`rounded px-3 py-1 text-xs ${
                selectedStageId === FULL_TREE_ID
                  ? "bg-emerald-500 text-slate-900"
                  : "bg-slate-800 text-slate-200 hover:bg-slate-700"
              }`}
            >
              Full Tree
            </button>
          </div>
          <p className="mb-2 text-xs text-slate-300">
            {STAGE_SUMMARIES[selectedViz.stage_id] ?? ""}
          </p>
          {stageSummaryText && (
            <div className="mb-2 w-full rounded border border-slate-800/60 bg-slate-900/60 p-3">
              <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">
                Completed Stage Summary
              </p>
              <div className="mt-1 text-xs leading-relaxed text-slate-200 whitespace-pre-wrap">
                {stageSummaryText}
              </div>
            </div>
          )}
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
            stageId={selectedViz.stage_id}
            bestNodeId={bestNodeForSelectedStage}
          />
        </>
      )}
    </div>
  );
}
