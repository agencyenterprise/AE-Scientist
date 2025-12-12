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

  // User selection - null means use default (first item)
  const [userSelectedStageId, setUserSelectedStageId] = useState<string | null>(null);

  // Derived selected stage ID - falls back to first item if user selection is invalid
  const selectedStageId = useMemo(() => {
    if (!hasViz) return null;
    // If user has selected a valid stage, use it
    if (userSelectedStageId && list.find(v => v.stage_id === userSelectedStageId)) {
      return userSelectedStageId;
    }
    // Otherwise default to first item
    return list[0]?.stage_id ?? null;
  }, [hasViz, list, userSelectedStageId]);

  const selectedViz =
    hasViz && selectedStageId ? (list.find(v => v.stage_id === selectedStageId) ?? list[0]) : null;

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
                onClick={() => setUserSelectedStageId(viz.stage_id)}
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
          <TreeVizViewer viz={selectedViz} artifacts={artifacts} />
        </>
      )}
    </div>
  );
}
