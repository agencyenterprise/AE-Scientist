import { ImportState } from "../types/types";

// URL patterns for supported chat services
export const CHATGPT_URL_PATTERN =
  /^https:\/\/chatgpt\.com\/share\/[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/;

export const BRANCHPROMPT_URL_PATTERN =
  /^https:\/\/v2\.branchprompt\.com\/conversation\/[a-f0-9]{24}$/;

export const CLAUDE_URL_PATTERN =
  /^https:\/\/claude\.ai\/share\/[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/;

export const GROK_URL_PATTERN = /^https:\/\/grok\.com\/share\//;

/**
 * Validates if a URL matches one of the supported chat service patterns
 */
export function validateUrl(url: string): boolean {
  const trimmed = url.trim();
  return (
    CHATGPT_URL_PATTERN.test(trimmed) ||
    BRANCHPROMPT_URL_PATTERN.test(trimmed) ||
    CLAUDE_URL_PATTERN.test(trimmed) ||
    GROK_URL_PATTERN.test(trimmed)
  );
}

/**
 * Returns a user-friendly message for the current import state
 */
export function getStateMessage(
  state: ImportState | "",
  isUpdateMode: boolean,
  summaryProgress?: number | null
): string {
  if (isUpdateMode) {
    switch (state) {
      case ImportState.Importing:
        return "Downloading updated conversation content...";
      case ImportState.Summarizing:
        return summaryProgress !== null
          ? `Summarizing conversation (${summaryProgress}%)...`
          : "Summarizing conversation...";
      case ImportState.Generating:
        return "Processing updates...";
      default:
        return "Updating conversation...";
    }
  } else {
    switch (state) {
      case ImportState.Importing:
        return "Downloading shared conversation...";
      case ImportState.ExtractingChatKeywords:
        return "Extracting chat keywords...";
      case ImportState.RetrievingMemories:
        return "Retrieving memories...";
      case ImportState.Summarizing:
        return summaryProgress !== null
          ? `Summarizing conversation (${summaryProgress}%)...`
          : "Summarizing conversation...";
      case ImportState.Generating:
        return "Generating project draft...";
      default:
        return "Processing...";
    }
  }
}

/**
 * Returns the validation error message for invalid URLs
 */
export function getUrlValidationError(): string {
  return "Invalid share URL. Expected ChatGPT https://chatgpt.com/share/{uuid}, BranchPrompt https://v2.branchprompt.com/conversation/{24-hex}, Claude https://claude.ai/share/{uuid}, or Grok https://grok.com/share/...";
}
