"use client";

import { Loader2 } from "lucide-react";
import { useMemo } from "react";

interface ChatGptUrlInputProps {
  url: string;
  onUrlChange: (value: string) => void;
  disabled?: boolean;
  error?: string | null;
  isExtracting?: boolean;
}

type PlatformType = "chatgpt" | "grok" | null;

/**
 * Detects the platform (ChatGPT or Grok) from the URL
 */
function detectPlatform(url: string): PlatformType {
  if (!url || url.trim() === "") return null;

  try {
    const urlLower = url.toLowerCase();

    // ChatGPT URLs: chatgpt.com, chat.openai.com
    if (urlLower.includes("chatgpt.com") || urlLower.includes("chat.openai.com")) {
      return "chatgpt";
    }

    // Grok URLs: grok.com/share, x.com/i/grok, grok.x.com
    if (
      urlLower.includes("grok.com/share") ||
      urlLower.includes("x.com/i/grok") ||
      urlLower.includes("grok.x.com")
    ) {
      return "grok";
    }

    return null;
  } catch {
    return null;
  }
}

export function ChatGptUrlInput({
  url,
  onUrlChange,
  disabled = false,
  error = null,
  isExtracting = false,
}: ChatGptUrlInputProps) {
  const isDisabled = disabled || isExtracting;

  // Detect platform from URL
  const platform = useMemo(() => detectPlatform(url), [url]);

  return (
    <div className="rounded-xl border border-slate-800/70 bg-slate-950/60 p-4 sm:rounded-2xl sm:p-5">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <label
          className="text-xs font-semibold uppercase tracking-[0.3em] text-slate-400"
          htmlFor="chatgpt-url"
        >
          Import share link
        </label>
      </div>
      <div className="mt-3 flex flex-col gap-3 md:flex-row md:items-center">
        <div className="relative flex-1">
          <input
            id="chatgpt-url"
            aria-describedby="chatgpt-url-help"
            placeholder="https://chatgpt.com/share/... or https://grok.com/share/..."
            className={`w-full rounded-xl border border-slate-700 bg-slate-900 py-3 pr-32 text-sm text-slate-100 placeholder:text-slate-500 outline-none transition focus:border-sky-500/50 focus:ring-2 focus:ring-sky-400/20 disabled:opacity-50 [&:-webkit-autofill]:bg-slate-900 [&:-webkit-autofill]:[-webkit-text-fill-color:rgb(241,245,249)] [&:-webkit-autofill]:shadow-[inset_0_0_0px_1000px_rgb(15,23,42)] [&:-webkit-autofill]:[-webkit-box-shadow:0_0_0px_1000px_rgb(15,23,42)_inset] ${platform ? "pl-4" : "px-4"}`}
            value={url}
            onChange={event => onUrlChange(event.target.value)}
            disabled={isDisabled}
          />
          {isExtracting && (
            <span className="pointer-events-none absolute right-2 top-1/2 inline-flex -translate-y-1/2 items-center gap-1 rounded-full border border-sky-500/30 bg-sky-500/10 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.3em] text-sky-200">
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              Extracting…
            </span>
          )}
        </div>
      </div>
      <p
        id="chatgpt-url-help"
        className={`mt-2 text-xs ${isExtracting ? "text-sky-200" : error ? "text-rose-400" : "text-slate-500"}`}
      >
        {isExtracting
          ? `Extracting conversation from ${platform === "grok" ? "Grok" : "ChatGPT"}. This usually takes under 30 seconds.`
          : error
            ? error
            : "Import conversation automatically - just paste a ChatGPT or Grok share link"}
      </p>
    </div>
  );
}
