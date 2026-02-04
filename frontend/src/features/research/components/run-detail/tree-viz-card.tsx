"use client";

import { useMemo, useState } from "react";
import type { TreeVizItem, ArtifactMetadata, SubstageSummary } from "@/types/research";
import { formatDateTime } from "@/shared/lib/date-utils";
import {
  stageLabel,
  extractStageSlug,
  getSummaryText,
  getStageSummary,
  getStageSlug,
  FULL_TREE_STAGE_ID,
} from "@/shared/lib/stage-utils";
import { TreeVizViewer } from "./tree-viz-viewer";
import { mergeTreeVizItems } from "@/shared/lib/tree-merge-utils";

interface Props {
  treeViz?: TreeVizItem[] | null;
  conversationId: number | null;
  runId: string;
  artifacts: ArtifactMetadata[];
  substageSummaries?: SubstageSummary[];
}

export function TreeVizCard({
  treeViz,
  conversationId,
  runId,
  artifacts,
  substageSummaries,
}: Props) {
  const list = useMemo(() => treeViz ?? [], [treeViz]);
  const hasViz = list.length > 0 && conversationId !== null;

  // Track the selected stage ID (defaults to Full Tree view)
  const [manuallySelectedStageId, setManuallySelectedStageId] = useState<string | null>(
    FULL_TREE_STAGE_ID
  );

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
      if (manuallySelectedStageId === FULL_TREE_STAGE_ID) {
        return FULL_TREE_STAGE_ID;
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
    if (selectedStageId === FULL_TREE_STAGE_ID) return mergedViz;
    return list.find(v => v.stage_id === selectedStageId) ?? list[0];
  }, [hasViz, selectedStageId, list, mergedViz]);

  // Find best node for the selected stage using the is_best_node array in the tree viz payload
  const bestNodeForSelectedStage = useMemo(() => {
    if (!selectedViz) {
      return null;
    }

    const payload = selectedViz.viz as { is_best_node?: boolean[] };
    const isBestNodeArray = payload.is_best_node;

    if (!isBestNodeArray || isBestNodeArray.length === 0) {
      return null;
    }

    // Find the index where is_best_node is true
    const bestNodeIndex = isBestNodeArray.findIndex(isBest => isBest === true);

    return bestNodeIndex >= 0 ? bestNodeIndex : null;
  }, [selectedViz]);

  const stageSummaryText = useMemo(() => {
    if (!selectedViz) return null;
    if (!substageSummaries || substageSummaries.length === 0) return null;
    if (selectedViz.stage_id === FULL_TREE_STAGE_ID) return null;

    const stageKey = getStageSlug(selectedViz.stage_id);
    if (!stageKey) return null;

    const matches = substageSummaries.filter(
      summary => extractStageSlug(summary.stage) === stageKey
    );
    if (matches.length === 0) return null;

    const latest =
      matches.sort(
        (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
      )[0] ?? null;
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
                setManuallySelectedStageId(FULL_TREE_STAGE_ID);
              }}
              className={`rounded px-3 py-1 text-xs ${
                selectedStageId === FULL_TREE_STAGE_ID
                  ? "bg-emerald-500 text-slate-900"
                  : "bg-slate-800 text-slate-200 hover:bg-slate-700"
              }`}
            >
              Full Tree
            </button>
          </div>
          <p className="mb-2 text-xs text-slate-300">
            {getStageSummary(selectedViz.stage_id) ?? ""}
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
            conversationId={conversationId}
            runId={runId}
            stageId={selectedViz.stage_id}
            bestNodeId={bestNodeForSelectedStage}
          />
        </>
      )}
    </div>
  );
}
