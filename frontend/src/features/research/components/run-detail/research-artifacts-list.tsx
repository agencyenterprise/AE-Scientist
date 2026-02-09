"use client";

import { useState, type ReactNode } from "react";
import {
  ChevronDown,
  ChevronRight,
  Download,
  FileCode,
  FileText,
  FolderArchive,
  MessageSquareText,
  Package,
  ScrollText,
} from "lucide-react";
import type { ArtifactMetadata, ArtifactType } from "@/types/research";
import { formatRelativeTime } from "@/shared/lib/date-utils";
import { formatFileSize } from "@/shared/lib/fileUtils";
import { useArtifactDownload } from "@/features/research/hooks/useArtifactDownload";

// Artifact type constants (must match generated ArtifactType)
export const ARTIFACT_TYPES = {
  PLOT: "plot",
  PAPER_PDF: "paper_pdf",
  LATEX_ARCHIVE: "latex_archive",
  WORKSPACE_ARCHIVE: "workspace_archive",
  LLM_REVIEW: "llm_review",
  RUN_LOG: "run_log",
} as const satisfies Record<string, ArtifactType>;

// Artifact type configuration with labels and icons
const ARTIFACT_TYPE_CONFIG: Record<
  ArtifactType,
  { label: string; icon: ReactNode; iconColor: string }
> = {
  [ARTIFACT_TYPES.PAPER_PDF]: {
    label: "Research Paper",
    icon: <FileText className="h-5 w-5" />,
    iconColor: "text-amber-400",
  },
  [ARTIFACT_TYPES.LATEX_ARCHIVE]: {
    label: "LaTeX Source",
    icon: <FileCode className="h-5 w-5" />,
    iconColor: "text-blue-400",
  },
  [ARTIFACT_TYPES.WORKSPACE_ARCHIVE]: {
    label: "Workspace Archive",
    icon: <FolderArchive className="h-5 w-5" />,
    iconColor: "text-purple-400",
  },
  [ARTIFACT_TYPES.LLM_REVIEW]: {
    label: "AI Review",
    icon: <MessageSquareText className="h-5 w-5" />,
    iconColor: "text-green-400",
  },
  [ARTIFACT_TYPES.RUN_LOG]: {
    label: "Run Log",
    icon: <ScrollText className="h-5 w-5" />,
    iconColor: "text-slate-400",
  },
  [ARTIFACT_TYPES.PLOT]: {
    label: "Plot",
    icon: <FileText className="h-5 w-5" />,
    iconColor: "text-slate-400",
  },
};

function getArtifactConfig(artifactType: ArtifactType) {
  return (
    ARTIFACT_TYPE_CONFIG[artifactType] ?? {
      label: artifactType,
      icon: <FileText className="h-5 w-5" />,
      iconColor: "text-slate-400",
    }
  );
}

interface ResearchArtifactsListProps {
  artifacts: ArtifactMetadata[];
  conversationId: number;
  runId: string;
}

interface ArtifactRowProps {
  artifact: ArtifactMetadata;
  downloadArtifact: (id: number) => void;
  isDownloading: boolean;
  downloadingArtifactId: number | null;
  indented?: boolean;
}

function ArtifactRow({
  artifact,
  downloadArtifact,
  isDownloading,
  downloadingArtifactId,
  indented = false,
}: ArtifactRowProps) {
  const config = getArtifactConfig(artifact.artifact_type);

  return (
    <div
      className={`flex items-center justify-between py-3 first:pt-0 last:pb-0 ${indented ? "pl-6" : ""}`}
    >
      <div className="flex items-center gap-3">
        <div
          className={`flex h-10 w-10 items-center justify-center rounded-lg bg-slate-800 ${config.iconColor}`}
        >
          {config.icon}
        </div>
        <div>
          <p className="font-medium text-white">{artifact.filename}</p>
          <p className="text-xs text-slate-400">
            {config.label} &middot; {formatFileSize(artifact.file_size)} &middot;{" "}
            {formatRelativeTime(artifact.created_at)}
          </p>
        </div>
      </div>
      <button
        onClick={() => downloadArtifact(artifact.id)}
        disabled={isDownloading}
        className="inline-flex items-center gap-1.5 rounded-lg bg-slate-800 px-3 py-2 text-sm font-medium text-slate-300 transition-colors hover:bg-slate-700 hover:text-white disabled:cursor-not-allowed disabled:opacity-50"
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
  );
}

interface PdfGroupProps {
  pdfs: ArtifactMetadata[];
  downloadArtifact: (id: number) => void;
  isDownloading: boolean;
  downloadingArtifactId: number | null;
}

function PdfGroup({ pdfs, downloadArtifact, isDownloading, downloadingArtifactId }: PdfGroupProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  if (pdfs.length === 0) return null;

  // Sort PDFs by creation date (newest first) or by numeric suffix
  const sortedPdfs = [...pdfs].sort((a, b) => {
    const extractSuffix = (filename: string): number => {
      const match = filename.match(/_(\d+)\.pdf$/);
      return match ? parseInt(match[1] ?? "0", 10) : 0;
    };
    const suffixDiff = extractSuffix(b.filename) - extractSuffix(a.filename);
    if (suffixDiff !== 0) return suffixDiff;
    return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
  });

  // Safe to assert since we check pdfs.length === 0 above
  const latestPdf = sortedPdfs[0]!;
  const olderPdfs = sortedPdfs.slice(1);

  if (pdfs.length === 1) {
    return (
      <ArtifactRow
        artifact={latestPdf}
        downloadArtifact={downloadArtifact}
        isDownloading={isDownloading}
        downloadingArtifactId={downloadingArtifactId}
      />
    );
  }

  const config = getArtifactConfig(latestPdf.artifact_type);

  return (
    <div className="py-3 first:pt-0 last:pb-0">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div
            className={`flex h-10 w-10 items-center justify-center rounded-lg bg-slate-800 ${config.iconColor}`}
          >
            {config.icon}
          </div>
          <div>
            <p className="font-medium text-white">{latestPdf.filename}</p>
            <p className="text-xs text-slate-400">
              {config.label} &middot; {formatFileSize(latestPdf.file_size)} &middot;{" "}
              {formatRelativeTime(latestPdf.created_at)}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="inline-flex items-center gap-1 rounded-lg bg-slate-800/50 px-2 py-1.5 text-xs font-medium text-slate-400 transition-colors hover:bg-slate-700 hover:text-slate-300"
          >
            {isExpanded ? (
              <ChevronDown className="h-3.5 w-3.5" />
            ) : (
              <ChevronRight className="h-3.5 w-3.5" />
            )}
            {olderPdfs.length} older version{olderPdfs.length > 1 ? "s" : ""}
          </button>
          <button
            onClick={() => downloadArtifact(latestPdf.id)}
            disabled={isDownloading}
            className="inline-flex items-center gap-1.5 rounded-lg bg-slate-800 px-3 py-2 text-sm font-medium text-slate-300 transition-colors hover:bg-slate-700 hover:text-white disabled:cursor-not-allowed disabled:opacity-50"
          >
            {downloadingArtifactId === latestPdf.id ? (
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
      </div>

      {isExpanded && (
        <div className="mt-2 border-l-2 border-slate-700 pl-4">
          {olderPdfs.map(pdf => (
            <ArtifactRow
              key={pdf.id}
              artifact={pdf}
              downloadArtifact={downloadArtifact}
              isDownloading={isDownloading}
              downloadingArtifactId={downloadingArtifactId}
              indented
            />
          ))}
        </div>
      )}
    </div>
  );
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

  // Filter out plot artifacts
  const filteredArtifacts = artifacts.filter(a => a.artifact_type !== ARTIFACT_TYPES.PLOT);

  // Separate PDFs from other artifacts
  const pdfArtifacts = filteredArtifacts.filter(a => a.artifact_type === ARTIFACT_TYPES.PAPER_PDF);
  const otherArtifacts = filteredArtifacts.filter(
    a => a.artifact_type !== ARTIFACT_TYPES.PAPER_PDF
  );

  if (filteredArtifacts.length === 0) {
    return null;
  }

  return (
    <div className="flex h-full flex-col rounded-2xl border border-slate-800 bg-slate-900/50 p-6">
      <div className="mb-4 flex items-center gap-2">
        <Package className="h-5 w-5 text-amber-400" />
        <h2 className="text-lg font-semibold text-white">Artifacts</h2>
      </div>
      <div className="min-h-0 flex-1 divide-y divide-slate-800 overflow-y-auto">
        {/* PDF Group */}
        {pdfArtifacts.length > 0 && (
          <PdfGroup
            pdfs={pdfArtifacts}
            downloadArtifact={downloadArtifact}
            isDownloading={isDownloading}
            downloadingArtifactId={downloadingArtifactId}
          />
        )}

        {/* Other Artifacts */}
        {otherArtifacts.map(artifact => (
          <ArtifactRow
            key={artifact.id}
            artifact={artifact}
            downloadArtifact={downloadArtifact}
            isDownloading={isDownloading}
            downloadingArtifactId={downloadingArtifactId}
          />
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
