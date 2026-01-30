import { useState } from "react";
import { api } from "@/shared/lib/api-client-typed";
import type { ArtifactPresignedUrlResponse } from "@/types/research";

interface UseArtifactDownloadOptions {
  conversationId: number;
  runId: string;
}

interface UseArtifactDownloadReturn {
  downloadArtifact: (artifactId: number) => Promise<void>;
  isDownloading: boolean;
  downloadingArtifactId: number | null;
  error: string | null;
}

/**
 * Hook for downloading artifacts via presigned S3 URLs.
 *
 * Fetches a presigned URL from the backend and redirects the browser
 * to trigger the download. Manages loading and error states.
 */
export function useArtifactDownload({
  conversationId,
  runId,
}: UseArtifactDownloadOptions): UseArtifactDownloadReturn {
  const [isDownloading, setIsDownloading] = useState(false);
  const [downloadingArtifactId, setDownloadingArtifactId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const downloadArtifact = async (artifactId: number) => {
    setIsDownloading(true);
    setDownloadingArtifactId(artifactId);
    setError(null);

    try {
      // Fetch presigned URL from backend
      const { data, error: fetchError } = await api.GET(
        "/api/conversations/{conversation_id}/idea/research-run/{run_id}/artifacts/{artifact_id}/presign",
        {
          params: {
            path: {
              conversation_id: conversationId,
              run_id: runId,
              artifact_id: artifactId,
            },
          },
        }
      );

      if (fetchError) throw new Error("Failed to fetch presigned URL");

      const response = data as ArtifactPresignedUrlResponse;

      // Redirect browser to presigned URL (triggers download)
      // window.location.href = response.url;
      const link = document.createElement("a");
      link.href = response.url;
      link.download = response.filename;
      link.target = "_blank";
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : "Failed to download artifact";
      setError(errorMessage);
    } finally {
      setIsDownloading(false);
      setDownloadingArtifactId(null);
    }
  };

  return {
    downloadArtifact,
    isDownloading,
    downloadingArtifactId,
    error,
  };
}
