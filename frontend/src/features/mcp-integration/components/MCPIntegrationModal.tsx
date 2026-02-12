"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plug } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/shared/components/ui/dialog";
import { Button } from "@/shared/components/ui/button";
import { CopyToClipboardButton } from "@/shared/components/CopyToClipboardButton";
import { config } from "@/shared/lib/config";
import { fetchMCPApiKey, generateMCPApiKey, revokeMCPApiKey } from "../api";

interface MCPIntegrationModalProps {
  trigger?: React.ReactNode;
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
}

export function MCPIntegrationModal({
  trigger,
  open: controlledOpen,
  onOpenChange,
}: MCPIntegrationModalProps) {
  const queryClient = useQueryClient();
  const [internalOpen, setInternalOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Support both controlled and uncontrolled modes
  const isControlled = controlledOpen !== undefined;
  const open = isControlled ? controlledOpen : internalOpen;

  const apiKeyQuery = useQuery({
    queryKey: ["mcp-integration", "key"],
    queryFn: fetchMCPApiKey,
    enabled: open,
  });

  const generateMutation = useMutation({
    mutationFn: generateMCPApiKey,
    onSuccess: () => {
      setError(null);
      queryClient.invalidateQueries({ queryKey: ["mcp-integration", "key"] });
    },
    onError: (err: Error) => {
      setError(err.message);
    },
  });

  const revokeMutation = useMutation({
    mutationFn: revokeMCPApiKey,
    onSuccess: () => {
      setError(null);
      queryClient.invalidateQueries({ queryKey: ["mcp-integration", "key"] });
    },
    onError: (err: Error) => {
      setError(err.message);
    },
  });

  const hasKey = apiKeyQuery.data?.has_key ?? false;
  const apiKey = apiKeyQuery.data?.api_key ?? "";

  // Build the MCP commands
  const mcpServerUrl = `${config.apiBaseUrl}/mcp`;
  const claudeCommand = `claude mcp add-json research-pipeline '{"type":"http","url":"${mcpServerUrl}","headers":{"Authorization":"Bearer ${apiKey}"}}'`;
  const cursorConfig = JSON.stringify(
    {
      mcpServers: {
        "research-pipeline": {
          url: mcpServerUrl,
          headers: {
            Authorization: `Bearer ${apiKey}`,
          },
        },
      },
    },
    null,
    2
  );

  const handleOpenChange = (isOpen: boolean) => {
    if (isControlled) {
      onOpenChange?.(isOpen);
    } else {
      setInternalOpen(isOpen);
    }
    if (!isOpen) {
      setError(null);
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      {!isControlled && (
        <DialogTrigger asChild>
          {trigger ?? (
            <button className="w-full rounded px-3 py-2 text-left text-sm text-slate-300 transition-colors hover:bg-slate-700 hover:text-white flex items-center gap-2">
              <Plug className="h-4 w-4" />
              Integrate with Claude/Cursor
            </button>
          )}
        </DialogTrigger>
      )}
      <DialogContent className="max-h-[90vh] overflow-hidden flex flex-col sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>MCP Integration</DialogTitle>
          <DialogDescription>
            Connect AE Scientist to Claude Code or Cursor to run research pipelines directly from
            your IDE.
          </DialogDescription>
        </DialogHeader>

        <div className="flex-1 overflow-y-auto space-y-4 pt-2">
          {error && (
            <div className="rounded-md bg-destructive/10 border border-destructive/30 px-4 py-3 text-sm text-destructive">
              {error}
            </div>
          )}

          {/* API Key Section */}
          <div className="space-y-3">
            <h3 className="text-sm font-medium text-foreground">API Key</h3>

            {apiKeyQuery.isLoading ? (
              <p className="text-sm text-muted-foreground">Loading...</p>
            ) : hasKey ? (
              <div className="space-y-3">
                <div className="flex items-center gap-2">
                  <code className="flex-1 rounded-md bg-muted px-2 py-2 font-mono text-[10px] md:text-sm text-foreground overflow-x-auto">
                    {apiKey}
                  </code>
                  <CopyToClipboardButton text={apiKey} label="Copy API key" />
                </div>

                <div className="flex gap-2">
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => generateMutation.mutate()}
                    disabled={generateMutation.isPending}
                  >
                    {generateMutation.isPending ? "Generating..." : "Regenerate Key"}
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => revokeMutation.mutate()}
                    disabled={revokeMutation.isPending}
                    className="text-red-400 border-red-500/60 hover:bg-red-500/10"
                  >
                    {revokeMutation.isPending ? "Revoking..." : "Revoke Key"}
                  </Button>
                </div>
              </div>
            ) : (
              <Button
                type="button"
                onClick={() => generateMutation.mutate()}
                disabled={generateMutation.isPending}
              >
                {generateMutation.isPending ? "Generating..." : "Generate API Key"}
              </Button>
            )}
          </div>

          {/* Setup Instructions - only shown when key exists */}
          {hasKey && (
            <>
              {/* Claude Code Setup */}
              <div className="space-y-3 pt-2 border-t border-border">
                <h3 className="text-sm font-medium text-foreground">Claude Code Setup</h3>
                <p className="text-sm text-muted-foreground">
                  Run this command in your terminal to add AE Scientist to Claude Code:
                </p>

                <div className="relative">
                  <pre className="overflow-x-auto whitespace-pre-wrap break-all rounded-md bg-slate-900 p-3 pr-10 font-mono text-[10px] md:text-xs text-slate-100">
                    {claudeCommand}
                  </pre>
                  <div className="absolute right-2 top-2">
                    <CopyToClipboardButton text={claudeCommand} label="Copy command" />
                  </div>
                </div>
              </div>

              {/* Cursor Setup */}
              <div className="space-y-3 pt-2 border-t border-border">
                <h3 className="text-sm font-medium text-foreground">Cursor Setup</h3>
                <p className="text-sm text-muted-foreground">
                  Add this to your{" "}
                  <code className="rounded bg-muted px-1 py-0.5 font-mono text-xs">
                    .cursor/mcp.json
                  </code>{" "}
                  file:
                </p>

                <div className="relative">
                  <pre className="overflow-x-auto whitespace-pre-wrap break-all rounded-md bg-slate-900 p-3 pr-10 font-mono text-[10px] md:text-xs text-slate-100">
                    {cursorConfig}
                  </pre>
                  <div className="absolute right-2 top-2">
                    <CopyToClipboardButton text={cursorConfig} label="Copy config" />
                  </div>
                </div>
              </div>

              {/* Usage note */}
              <p className="text-xs text-muted-foreground pt-2">
                After setup, you can use the{" "}
                <code className="rounded bg-muted px-1 py-0.5 font-mono text-xs">run_pipeline</code>{" "}
                tool to start research runs.
              </p>
            </>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
