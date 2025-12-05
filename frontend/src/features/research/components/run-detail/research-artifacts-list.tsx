"use client";

import { Download, FileText, Package } from "lucide-react";
import type { ArtifactMetadata } from "@/types/research";
import { formatBytes, formatRelativeTime } from "@/shared/lib/date-utils";
import { useArtifactDownload } from "@/features/research/hooks/useArtifactDownload";

interface ResearchArtifactsListProps {
  artifacts: ArtifactMetadata[];
  conversationId: number;
  runId: string;
}

/**
 * Artifacts list section for research run detail page
 */
export function ResearchArtifactsList({
  artifacts,
  conversationId,
  runId,
}: ResearchArtifactsListProps) {
  const { downloadArtifact, isDownloading, downloadingArtifactId, error } = useArtifactDownload({
    conversationId,
    runId,
  });
  if (artifacts.length === 0) {
    return null;
  }

  return (
    <div className="flex h-full flex-col rounded-xl border border-slate-800 bg-slate-900/50 p-6">
      <div className="mb-4 flex items-center gap-2">
        <Package className="h-5 w-5 text-amber-400" />
        <h2 className="text-lg font-semibold text-white">Artifacts</h2>
      </div>
      <div className="min-h-0 flex-1 divide-y divide-slate-800 overflow-y-auto">
        {artifacts.map(artifact => (
          <div
            key={artifact.id}
            className="flex items-center justify-between py-3 first:pt-0 last:pb-0"
          >
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-slate-800">
                <FileText className="h-5 w-5 text-slate-400" />
              </div>
              <div>
                <p className="font-medium text-white">{artifact.filename}</p>
                <p className="text-xs text-slate-400">
                  {artifact.artifact_type} &middot; {formatBytes(artifact.file_size)} &middot;{" "}
                  {formatRelativeTime(artifact.created_at)}
                </p>
              </div>
            </div>
            <button
              onClick={() => downloadArtifact(artifact.id)}
              disabled={isDownloading}
              className="inline-flex items-center gap-1.5 rounded-lg bg-slate-800 px-3 py-2 text-sm font-medium text-slate-300 transition-colors hover:bg-slate-700 hover:text-white disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {downloadingArtifactId === artifact.id ? (
                <>
                  <div className="h-4 w-4 animate-pulse">...</div>
                  <span>Downloading...</span>
                </>
              ) : (
                <>
                  <Download className="h-4 w-4" />
                  Download
                </>
              )}
            </button>
          </div>
        ))}
      </div>

      {/* Error Message */}
      {error && (
        <div className="mt-3 rounded border border-red-800 bg-red-950/30 px-3 py-2 text-sm text-red-400">
          {error}
        </div>
      )}
    </div>
  );
}
