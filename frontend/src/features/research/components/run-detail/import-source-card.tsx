"use client";

import { ExternalLink, MessageSquare } from "lucide-react";

interface ImportSourceCardProps {
  conversationUrl: string;
}

/**
 * Detects the platform from a conversation URL
 */
function detectPlatform(url: string): {
  name: string;
  displayName: string;
} {
  if (url.includes("chatgpt.com")) {
    return { name: "chatgpt", displayName: "ChatGPT" };
  }
  if (url.includes("claude.ai")) {
    return { name: "claude", displayName: "Claude" };
  }
  if (url.includes("grok.com")) {
    return { name: "grok", displayName: "Grok" };
  }
  if (url.includes("branchprompt.com")) {
    return { name: "branchprompt", displayName: "BranchPrompt" };
  }
  return { name: "unknown", displayName: "External" };
}

/**
 * Card displaying the source conversation link for imported research runs.
 * Shows when a research run was generated from an imported conversation (ChatGPT, Claude, etc.)
 */
export function ImportSourceCard({ conversationUrl }: ImportSourceCardProps) {
  const platform = detectPlatform(conversationUrl);

  return (
    <div className="rounded-lg border border-blue-800/50 bg-gradient-to-r from-blue-950/30 to-blue-900/20 p-4">
      <div className="flex items-center gap-3">
        <div className="flex h-8 w-8 items-center justify-center rounded-full bg-blue-500/20">
          <MessageSquare className="h-4 w-4 text-blue-400" />
        </div>
        <div className="flex-1">
          <div className="text-sm font-medium text-blue-100">
            Imported from {platform.displayName}
          </div>
          <div className="mt-0.5 text-xs text-blue-300/70">
            This research was generated from an imported conversation
          </div>
        </div>
        <a
          href={conversationUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-2 rounded border border-blue-600/50 bg-blue-500/10 px-3 py-2 text-sm font-medium text-blue-100 transition-colors hover:bg-blue-500/20 hover:border-blue-500"
        >
          <span>View Original</span>
          <ExternalLink className="h-3.5 w-3.5" />
        </a>
      </div>
    </div>
  );
}


