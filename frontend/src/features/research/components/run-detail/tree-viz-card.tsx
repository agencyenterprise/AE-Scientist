"use client";

import { useMemo, useState } from "react";
import type { TreeVizItem, ArtifactMetadata } from "@/types/research";
import { TreeVizViewer } from "./tree-viz-viewer";

interface Props {
  treeViz?: TreeVizItem[] | null;
  conversationId: number | null;
  artifacts: ArtifactMetadata[];
}

export function TreeVizCard({ treeViz, conversationId, artifacts }: Props) {
  const list = useMemo(() => treeViz ?? [], [treeViz]);
  const hasViz = list.length > 0 && conversationId !== null;

  // Track whether user has manually selected a stage (null = auto-follow mode)
  const [manuallySelectedStageId, setManuallySelectedStageId] = useState<string | null>(null);
  
  // Compute the most recent stage ID
  const mostRecentStageId = useMemo(() => {
    if (!hasViz) return null;
    const sortedByDate = [...list].sort((a, b) => 
      new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
    );
    return sortedByDate[0]?.stage_id ?? null;
  }, [hasViz, list]);

  // Derived selected stage ID - uses manual selection if set, otherwise auto-follows most recent
  const selectedStageId = useMemo(() => {
    if (!hasViz) return null;
    
    // If user has manually selected a stage and it still exists, use it
    if (manuallySelectedStageId && list.find(v => v.stage_id === manuallySelectedStageId)) {
      console.log('[TreeVizCard] Using manual selection:', manuallySelectedStageId);
      return manuallySelectedStageId;
    }
    
    // Otherwise auto-follow the most recent stage
    console.log('[TreeVizCard] Auto-following most recent stage:', mostRecentStageId);
    return mostRecentStageId;
  }, [hasViz, list, manuallySelectedStageId, mostRecentStageId]);

  const selectedViz =
    hasViz && selectedStageId ? (list.find(v => v.stage_id === selectedStageId) ?? list[0]) : null;

  // Find best node for the selected stage using the is_best_node array in the tree viz payload
  const bestNodeForSelectedStage = useMemo(() => {
    console.log('[TreeVizCard] Computing best node for stage:', {
      selectedStageId,
      hasSelectedViz: !!selectedViz,
    });
    
    if (!selectedViz) {
      console.log('[TreeVizCard] No selectedViz, returning null');
      return null;
    }
    
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const payload = selectedViz.viz as any;
    const isBestNodeArray = payload?.is_best_node;
    
    console.log('[TreeVizCard] Tree viz payload:', {
      hasPayload: !!payload,
      hasBestNodeArray: !!isBestNodeArray,
      bestNodeArrayLength: isBestNodeArray?.length,
      bestNodeArray: isBestNodeArray,
    });
    
    if (!isBestNodeArray || isBestNodeArray.length === 0) {
      console.log('[TreeVizCard] No is_best_node array, returning null');
      return null;
    }
    
    // Find the index where is_best_node is true
    const bestNodeIndex = isBestNodeArray.findIndex((isBest: boolean) => isBest === true);
    
    console.log('[TreeVizCard] Best node index found:', bestNodeIndex);
    
    return bestNodeIndex >= 0 ? bestNodeIndex : null;
  }, [selectedViz, selectedStageId]);

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
                  console.log('[TreeVizCard] User manually selected stage:', viz.stage_id);
                  setManuallySelectedStageId(viz.stage_id);
                }}
                className={`rounded px-3 py-1 text-xs ${
                  viz.stage_id === selectedStageId
                    ? "bg-emerald-500 text-slate-900"
                    : "bg-slate-800 text-slate-200 hover:bg-slate-700"
                }`}
              >
                {viz.stage_id.replace("Stage_", "Stage ")}
              </button>
            ))}
          </div>
          <div className="flex items-center justify-between text-xs text-slate-400 mb-2">
            <span>
              Stage {selectedViz.stage_id} • Version {selectedViz.version} •{" "}
              {new Date(selectedViz.updated_at).toLocaleString()}
            </span>
          </div>
          <TreeVizViewer viz={selectedViz} artifacts={artifacts} bestNodeId={bestNodeForSelectedStage} />
        </>
      )}
    </div>
  );
}
