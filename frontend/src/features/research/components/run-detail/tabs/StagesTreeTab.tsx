"use client";

import { TreeVizCard } from "../tree-viz-card";
import type { ArtifactMetadata, SubstageSummary, TreeVizItem } from "@/types/research";

interface TreeTabProps {
  treeViz: TreeVizItem[];
  conversationId: number | null;
  runId: string;
  artifacts: ArtifactMetadata[];
  substageSummaries: SubstageSummary[];
}

export function TreeTab({
  treeViz,
  conversationId,
  runId,
  artifacts,
  substageSummaries,
}: TreeTabProps) {
  if (conversationId === null) {
    return null;
  }

  return (
    <TreeVizCard
      treeViz={treeViz}
      conversationId={conversationId}
      runId={runId}
      artifacts={artifacts}
      substageSummaries={substageSummaries}
    />
  );
}
