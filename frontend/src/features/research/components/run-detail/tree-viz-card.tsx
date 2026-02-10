"use client";

import { useMemo, useState } from "react";
import type { TreeVizItem, ArtifactMetadata } from "@/types/research";
import {
  stageLabel,
  getStageSummary,
  STAGE_ID,
  FULL_TREE_STAGE_ID,
} from "@/shared/lib/stage-utils";
import { TreeVizViewer } from "./tree-viz-viewer";
import { mergeTreeVizItems } from "@/shared/lib/tree-merge-utils";
import {
  HelpCircle,
  GitBranch,
  CheckCircle2,
  Sparkles,
  FlaskConical,
  FileText,
} from "lucide-react";
import { Tooltip, TooltipTrigger, TooltipContent } from "@/shared/components/ui/tooltip";
import { cn } from "@/shared/lib/utils";

interface Props {
  treeViz?: TreeVizItem[] | null;
  conversationId: number | null;
  runId: string;
  artifacts: ArtifactMetadata[];
}

// Stage configuration with icons and colors for visual hierarchy
const STAGE_CONFIG: Record<string, { icon: React.ReactNode; color: string; description: string }> =
  {
    [STAGE_ID.INITIAL_IMPLEMENTATION]: {
      icon: <CheckCircle2 className="h-3.5 w-3.5" />,
      color: "emerald",
      description: "Building the foundation - creating a working baseline implementation",
    },
    [STAGE_ID.BASELINE_TUNING]: {
      icon: <FlaskConical className="h-3.5 w-3.5" />,
      color: "blue",
      description: "Fine-tuning parameters to optimize baseline performance",
    },
    [STAGE_ID.CREATIVE_RESEARCH]: {
      icon: <Sparkles className="h-3.5 w-3.5" />,
      color: "purple",
      description: "Exploring novel improvements and generating visualizations",
    },
    [STAGE_ID.ABLATION_STUDIES]: {
      icon: <GitBranch className="h-3.5 w-3.5" />,
      color: "amber",
      description: "Testing which components contribute most to the results",
    },
    [STAGE_ID.PAPER_GENERATION]: {
      icon: <FileText className="h-3.5 w-3.5" />,
      color: "rose",
      description: "Compiling findings into a research paper",
    },
  };

// Get stage config with fallback
function getStageConfig(stageId: string) {
  return (
    STAGE_CONFIG[stageId] ?? {
      icon: <GitBranch className="h-3.5 w-3.5" />,
      color: "slate",
      description: "Research exploration stage",
    }
  );
}

export function TreeVizCard({ treeViz, conversationId, runId, artifacts }: Props) {
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
    return sortedByDate[0]?.stage ?? null;
  }, [hasViz, list]);

  // Derived selected stage ID - uses manual selection if set, otherwise auto-follows most recent
  const selectedStageId = useMemo(() => {
    if (!hasViz) return null;

    // If user has manually selected Full Tree or a stage that still exists, use it
    if (manuallySelectedStageId) {
      if (manuallySelectedStageId === FULL_TREE_STAGE_ID) {
        return FULL_TREE_STAGE_ID;
      }
      if (list.find(v => v.stage === manuallySelectedStageId)) {
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
    return list.find(v => v.stage === selectedStageId) ?? list[0];
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
          </TooltipContent>
        </Tooltip>
      </div>

      {!hasViz && (
        <div className="text-center py-8">
          <GitBranch className="h-12 w-12 text-slate-600 mx-auto mb-3" />
          <p className="text-sm text-slate-400">No tree visualization available yet.</p>
          <p className="text-xs text-slate-500 mt-1">
            The tree will appear as the research progresses.
          </p>
        </div>
      )}

      {hasViz && selectedViz && (
        <>
          {/* Stage selector with improved visual hierarchy */}
          <div className="mb-4">
            <p className="text-xs text-slate-400 mb-2">
              Select a stage to view its exploration tree:
            </p>
            <div className="flex flex-wrap gap-2">
              {list.map(viz => {
                const config = getStageConfig(viz.stage);
                const isSelected = viz.stage === selectedStageId;
                return (
                  <Tooltip key={`${viz.stage}-${viz.id}`}>
                    <TooltipTrigger asChild>
                      <button
                        type="button"
                        onClick={() => setManuallySelectedStageId(viz.stage)}
                        className={cn(
                          "flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-all",
                          isSelected
                            ? "bg-emerald-500 text-slate-900 shadow-md shadow-emerald-500/20"
                            : "bg-slate-800 text-slate-300 hover:bg-slate-700 hover:text-white"
                        )}
                        aria-pressed={isSelected}
                      >
                        {config.icon}
                        <span>{stageLabel(viz.stage)}</span>
                      </button>
                    </TooltipTrigger>
                    <TooltipContent
                      side="bottom"
                      className="bg-slate-800 text-slate-200 border-slate-700 text-xs py-1.5 px-2"
                    >
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
                <TooltipContent
                  side="bottom"
                  className="bg-slate-800 text-slate-200 border-slate-700 text-xs py-1.5 px-2"
                >
                  View the complete research tree across all stages
                </TooltipContent>
              </Tooltip>
            </div>
          </div>

          {/* Stage description */}
          <StageDescription summary={getStageSummary(selectedViz.stage)} />

          {/* Tree visualization */}
          <TreeVizViewer
            viz={selectedViz}
            artifacts={artifacts}
            conversationId={conversationId}
            runId={runId}
            stageId={selectedViz.stage}
            bestNodeId={bestNodeForSelectedStage}
          />
        </>
      )}
    </div>
  );
}

function StageDescription({ summary }: { summary: string | null | undefined }) {
  if (!summary) return null;

  // Check if the summary starts with "Goal:"
  if (summary.startsWith("Goal:")) {
    const rest = summary.slice(5).trim();
    return (
      <p className="mb-4 text-sm text-slate-300">
        <span className="font-semibold text-emerald-400">Goal:</span> {rest}
      </p>
    );
  }

  return <p className="mb-4 text-sm text-slate-300">{summary}</p>;
}
