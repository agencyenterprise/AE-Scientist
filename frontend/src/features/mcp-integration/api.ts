"use client";

import { api } from "@/shared/lib/api-client-typed";
import type { components } from "@/types/api.gen";

export type MCPApiKeyResponse = components["schemas"]["MCPApiKeyResponse"];
export type MCPApiKeyGeneratedResponse = components["schemas"]["MCPApiKeyGeneratedResponse"];
export type MCPApiKeyRevokedResponse = components["schemas"]["MCPApiKeyRevokedResponse"];

export async function fetchMCPApiKey(): Promise<MCPApiKeyResponse> {
  const { data, error } = await api.GET("/api/mcp-integration/key");
  if (error) throw new Error("Failed to fetch MCP API key");
  return data as MCPApiKeyResponse;
}

export async function generateMCPApiKey(): Promise<MCPApiKeyGeneratedResponse> {
  const { data, error } = await api.POST("/api/mcp-integration/generate-key");
  if (error) throw new Error("Failed to generate MCP API key");
  return data as MCPApiKeyGeneratedResponse;
}

export async function revokeMCPApiKey(): Promise<MCPApiKeyRevokedResponse> {
  const { data, error } = await api.DELETE("/api/mcp-integration/key");
  if (error) throw new Error("Failed to revoke MCP API key");
  return data as MCPApiKeyRevokedResponse;
}
