"use client";

import { TreeVizCard } from "../tree-viz-card";
import type { ArtifactMetadata, TreeVizItem } from "@/types/research";

interface TreeTabProps {
  treeViz: TreeVizItem[];
  conversationId: number | null;
  runId: string;
  artifacts: ArtifactMetadata[];
}

export function TreeTab({ treeViz, conversationId, runId, artifacts }: TreeTabProps) {
  if (conversationId === null) {
    return null;
  }

  return (
    <TreeVizCard
      treeViz={treeViz}
      conversationId={conversationId}
      runId={runId}
      artifacts={artifacts}
    />
  );
}
