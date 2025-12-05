import { useState } from "react";
import { apiFetch } from "@/shared/lib/api-client";
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
      const response = await apiFetch<ArtifactPresignedUrlResponse>(
        `/conversations/${conversationId}/idea/research-run/${runId}/artifacts/${artifactId}/presign`
      );

      // Redirect browser to presigned URL (triggers download)
      window.location.href = response.url;
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
