"use client";

import { config } from "./config";
import { withAuthHeaders } from "./session-token";

function resolveDownloadUrl(path: string): string {
  if (!path) {
    throw new Error("Download path is required");
  }

  if (path.startsWith("http://") || path.startsWith("https://")) {
    return path;
  }

  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  if (normalizedPath.startsWith("/api")) {
    return `${config.apiBaseUrl}${normalizedPath}`;
  }

  return `${config.apiUrl}${normalizedPath}`;
}

export async function fetchDownloadUrl(downloadPath: string): Promise<string> {
  const url = resolveDownloadUrl(downloadPath);
  const headers = withAuthHeaders(new Headers({ Accept: "application/json" }));
  const response = await fetch(url, { headers });

  if (!response.ok) {
    throw new Error(`Failed to fetch download URL (HTTP ${response.status})`);
  }

  const data = (await response.json()) as { url?: string };
  if (!data?.url) {
    throw new Error("Download URL missing in response");
  }

  return data.url;
}
