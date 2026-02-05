export interface PlatformInfo {
  name: string;
  displayName: string;
}

/**
 * Detects the platform from a conversation URL
 */
export function detectPlatform(url: string): PlatformInfo | null {
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
  return null;
}
