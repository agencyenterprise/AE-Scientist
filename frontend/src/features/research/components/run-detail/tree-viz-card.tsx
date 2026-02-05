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
import { HelpCircle, GitBranch, CheckCircle2, Sparkles, FlaskConical, FileText } from "lucide-react";
import {
  Tooltip,
  TooltipTrigger,
  TooltipContent,
} from "@/shared/components/ui/tooltip";
import { cn } from "@/shared/lib/utils";

interface Props {
  treeViz?: TreeVizItem[] | null;
  conversationId: number | null;
  runId: string;
  artifacts: ArtifactMetadata[];
  substageSummaries?: SubstageSummary[];
}

// Stage configuration with icons and colors for visual hierarchy
const STAGE_CONFIG: Record<string, { icon: React.ReactNode; color: string; description: string }> = {
  initial_implementation: {
    icon: <CheckCircle2 className="h-3.5 w-3.5" />,
    color: "emerald",
    description: "Building the foundation - creating a working baseline implementation",
  },
  baseline_tuning: {
    icon: <FlaskConical className="h-3.5 w-3.5" />,
    color: "blue",
    description: "Fine-tuning parameters to optimize baseline performance",
  },
  creative_research: {
    icon: <Sparkles className="h-3.5 w-3.5" />,
    color: "purple",
    description: "Exploring novel improvements and generating visualizations",
  },
  ablation_studies: {
    icon: <GitBranch className="h-3.5 w-3.5" />,
    color: "amber",
    description: "Testing which components contribute most to the results",
  },
  paper_generation: {
    icon: <FileText className="h-3.5 w-3.5" />,
    color: "rose",
    description: "Compiling findings into a research paper",
  },
};

// Get stage config with fallback
function getStageConfig(stageId: string) {
  const slug = getStageSlug(stageId);
  return STAGE_CONFIG[slug ?? ""] ?? {
    icon: <GitBranch className="h-3.5 w-3.5" />,
    color: "slate",
    description: "Research exploration stage",
  };
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
    <div className="w-full rounded-2xl border border-slate-800 bg-slate-900/60 p-4 sm:p-6">
      {/* Header with help tooltip */}
      <div className="mb-4 flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <GitBranch className="h-5 w-5 text-emerald-400 flex-shrink-0" />
          <span className="text-base font-semibold text-slate-100">Research Tree</span>
        </div>
        <Tooltip>
          <TooltipTrigger asChild>
            <button
              type="button"
              className="flex items-center gap-1 text-xs text-slate-400 hover:text-slate-300 transition-colors"
              aria-label="What is this visualization?"
            >
              <HelpCircle className="h-4 w-4" />
              <span className="hidden sm:inline">What is this?</span>
            </button>
          </TooltipTrigger>
          <TooltipContent
            side="bottom"
            align="end"
            className="max-w-sm bg-slate-800 text-slate-200 border-slate-700 p-4"
          >
            <p className="font-medium mb-2">Understanding the Research Tree</p>
            <p className="text-xs text-slate-300 mb-2">
              This visualization shows how the AI explores different approaches during research.
              Each node represents an experiment, and branches show the exploration path.
            </p>
            <ul className="text-xs text-slate-300 space-y-1">
              <li className="flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-emerald-500" />
                <span>Best performing approach (highlighted)</span>
              </li>
              <li className="flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-blue-500" />
                <span>Successful experiments</span>
              </li>
              <li className="flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-slate-500" />
                <span>Explored alternatives</span>
              </li>
            </ul>
          </TooltipContent>
        </Tooltip>
      </div>

      {!hasViz && (
        <div className="text-center py-8">
          <GitBranch className="h-12 w-12 text-slate-600 mx-auto mb-3" />
          <p className="text-sm text-slate-400">No tree visualization available yet.</p>
          <p className="text-xs text-slate-500 mt-1">The tree will appear as the research progresses.</p>
        </div>
      )}

      {hasViz && selectedViz && (
        <>
          {/* Stage selector with improved visual hierarchy */}
          <div className="mb-4">
            <p className="text-xs text-slate-400 mb-2">Select a stage to view its exploration tree:</p>
            <div className="flex flex-wrap gap-2">
              {list.map(viz => {
                const config = getStageConfig(viz.stage_id);
                const isSelected = viz.stage_id === selectedStageId;
                return (
                  <Tooltip key={`${viz.stage_id}-${viz.id}`}>
                    <TooltipTrigger asChild>
                      <button
                        type="button"
                        onClick={() => setManuallySelectedStageId(viz.stage_id)}
                        className={cn(
                          "flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-all",
                          isSelected
                            ? "bg-emerald-500 text-slate-900 shadow-md shadow-emerald-500/20"
                            : "bg-slate-800 text-slate-300 hover:bg-slate-700 hover:text-white"
                        )}
                        aria-pressed={isSelected}
                      >
                        {config.icon}
                        <span>{stageLabel(viz.stage_id)}</span>
                      </button>
                    </TooltipTrigger>
                    <TooltipContent side="bottom" className="max-w-xs bg-slate-800 text-slate-200 border-slate-700">
                      {config.description}
                    </TooltipContent>
                  </Tooltip>
                );
              })}
              <Tooltip>
                <TooltipTrigger asChild>
                  <button
                    type="button"
                    onClick={() => setManuallySelectedStageId(FULL_TREE_STAGE_ID)}
                    className={cn(
                      "flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-all",
                      selectedStageId === FULL_TREE_STAGE_ID
                        ? "bg-emerald-500 text-slate-900 shadow-md shadow-emerald-500/20"
                        : "bg-slate-800 text-slate-300 hover:bg-slate-700 hover:text-white"
                    )}
                    aria-pressed={selectedStageId === FULL_TREE_STAGE_ID}
                  >
                    <GitBranch className="h-3.5 w-3.5" />
                    <span>Full Tree</span>
                  </button>
                </TooltipTrigger>
                <TooltipContent side="bottom" className="max-w-xs bg-slate-800 text-slate-200 border-slate-700">
                  View the complete research tree across all stages
                </TooltipContent>
              </Tooltip>
            </div>
          </div>

          {/* Stage description */}
          <div className="mb-4 text-sm text-slate-300">
            {getStageSummary(selectedViz.stage_id) ?? ""}
          </div>

          {/* Stage summary */}
          {stageSummaryText && (
            <div className="mb-4 w-full rounded-lg border border-emerald-500/20 bg-emerald-500/5 p-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-emerald-400 mb-2">
                Stage Summary
              </p>
              <div className="text-sm leading-relaxed text-slate-200 whitespace-pre-wrap">
                {stageSummaryText}
              </div>
            </div>
          )}

          {/* Timestamps */}
          <div className="mb-4 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-400">
            <span>
              <span className="text-slate-500">Started:</span>{" "}
              {formatDateTime(selectedViz.created_at)}
            </span>
            <span>
              <span className="text-slate-500">Updated:</span> {formatDateTime(selectedViz.updated_at)}
            </span>
          </div>

          {/* Tree visualization */}
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
