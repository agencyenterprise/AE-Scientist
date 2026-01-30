"use client";

import { ResearchArtifactsList } from "../../../components/run-detail/research-artifacts-list";
import type { ArtifactMetadata } from "@/types/research";

interface ArtifactsTabProps {
  artifacts: ArtifactMetadata[];
  conversationId: number | null;
  runId: string;
}

export function ArtifactsTab({ artifacts, conversationId, runId }: ArtifactsTabProps) {
  if (conversationId === null) {
    return (
      <div className="flex h-64 items-center justify-center">
        <p className="text-sm text-slate-400">Conversation not yet available.</p>
      </div>
    );
  }

  return (
    <ResearchArtifactsList artifacts={artifacts} conversationId={conversationId} runId={runId} />
  );
}
