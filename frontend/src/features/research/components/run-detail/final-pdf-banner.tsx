"use client";

import { Download, FileText, FolderArchive } from "lucide-react";
import type { ArtifactMetadata } from "@/types/research";
import { formatBytes } from "@/shared/lib/date-utils";
import { useArtifactDownload } from "@/features/research/hooks/useArtifactDownload";

interface FinalPdfBannerProps {
  artifacts: ArtifactMetadata[];
  conversationId: number;
  runId: string;
}

/**
 * Prominent banner for downloading final research results.
 * Shows final PDF paper and workspace archive when available.
 */
export function FinalPdfBanner({ artifacts, conversationId, runId }: FinalPdfBannerProps) {
  const { downloadArtifact, isDownloading, downloadingArtifactId, error } = useArtifactDownload({
    conversationId,
    runId,
  });
  // Find the final paper PDF (highest suffix or most recent)
  const paperPdfs = artifacts
    .filter(a => a.artifact_type === "paper_pdf")
    .sort((a, b) => {
      // Try to extract numeric suffix from filename (e.g., "paper_5.pdf" -> 5)
      const extractSuffix = (filename: string): number => {
        const match = filename.match(/_(\d+)\.pdf$/);
        return match ? parseInt(match[1] ?? "0", 10) : 0;
      };

      const suffixA = extractSuffix(a.filename);
      const suffixB = extractSuffix(b.filename);

      if (suffixA !== suffixB) {
        return suffixB - suffixA; // Higher suffix first
      }

      // Fallback to created_at if no suffix or equal
      return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
    });

  // Get only the final PDF (highest suffix)
  const finalPdf = paperPdfs.length > 0 ? paperPdfs[0] : null;

  // Find the workspace archive artifact
  const workspaceArchive = artifacts.find(a => a.artifact_type === "workspace_archive");

  // Don't render if no final PDF and no workspace archive
  if (!finalPdf && !workspaceArchive) {
    return null;
  }

  return (
    <div className="rounded-lg border border-emerald-800 bg-gradient-to-r from-emerald-950/50 to-emerald-900/30 p-6">
      {/* Header */}
      <div className="mb-4 flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-full bg-emerald-500/20">
          <FileText className="h-6 w-6 text-emerald-400" />
        </div>
        <div>
          <h3 className="text-base font-semibold text-emerald-100">Final Results Ready</h3>
          <p className="text-sm text-emerald-300/80">
            Download the final paper and experiment artifacts
          </p>
        </div>
      </div>

      {/* Download Cards - Two Column Layout */}
      <div className="grid gap-3 md:grid-cols-2">
        {/* Left Column: Final Paper PDF (50%) */}
        {finalPdf && (
          <div className="flex items-center justify-between rounded-lg border border-emerald-700/50 bg-emerald-950/30 p-4">
            <div className="flex items-start gap-3">
              <FileText className="h-5 w-5 flex-shrink-0 text-emerald-400" />
              <div className="flex-1">
                <div className="text-sm font-semibold text-emerald-100">Final Paper (PDF)</div>
                <div className="mt-1 text-xs text-emerald-400/70">
                  {finalPdf.file_size ? formatBytes(finalPdf.file_size) : "Unknown size"}
                </div>
              </div>
            </div>
            <button
              onClick={() => downloadArtifact(finalPdf.id)}
              disabled={isDownloading}
              className="flex items-center justify-center gap-2 rounded border border-emerald-600 bg-emerald-500/20 px-4 py-2.5 text-sm font-medium text-emerald-100 transition-colors hover:bg-emerald-500/30 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {downloadingArtifactId === finalPdf.id ? (
                <>
                  <div className="h-4 w-4 animate-pulse">...</div>
                  <span>Downloading...</span>
                </>
              ) : (
                <>
                  <Download className="h-4 w-4 text-emerald-100" />
                  <span className="text-emerald-100">Download</span>
                </>
              )}
            </button>
          </div>
        )}

        {/* Right Column: Workspace Archive (50%) */}
        {workspaceArchive && (
          <div className="flex items-center justify-between rounded-lg border border-emerald-700/50 bg-emerald-950/30 p-4">
            <div className="flex items-start gap-3">
              <FolderArchive className="h-5 w-5 flex-shrink-0 text-emerald-400" />
              <div className="flex-1">
                <div className="text-sm font-semibold text-emerald-100">Experiment Archive</div>
                <div className="mt-1 text-xs text-emerald-400/70">
                  {workspaceArchive.file_size
                    ? formatBytes(workspaceArchive.file_size)
                    : "Unknown size"}{" "}
                  &middot; Complete experiment data
                </div>
                <div className="mt-2 text-xs text-emerald-400/50">
                  Includes code, logs, plots, and all intermediate artifacts
                </div>
              </div>
            </div>
            <button
              onClick={() => downloadArtifact(workspaceArchive.id)}
              disabled={isDownloading}
              className="flex items-center justify-center gap-2 rounded border border-emerald-600 bg-emerald-500/20 px-4 py-2.5 text-sm font-medium text-emerald-100 transition-colors hover:bg-emerald-500/30 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {downloadingArtifactId === workspaceArchive.id ? (
                <>
                  <div className="h-4 w-4 animate-pulse">...</div>
                  <span>Downloading...</span>
                </>
              ) : (
                <>
                  <Download className="h-4 w-4 text-emerald-100" />
                  <span className="text-emerald-100">Download</span>
                </>
              )}
            </button>
          </div>
        )}
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
