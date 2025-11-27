"use client";

import React, { useMemo } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeHighlight from "rehype-highlight";
import rehypeKatex from "rehype-katex";
import "katex/dist/katex.min.css";

type MarkdownProps = {
  children: string;
  className?: string;
};

// Heuristic LaTeX auto-wrap similar to user's other app (kept minimal)
const latexPatterns: RegExp[] = [/\\frac\{[^}]*\}\{[^}]*\}/, /\\sqrt\{[^}]*\}/, /\\[a-zA-Z]+\b/];

function ensureListBlankLines(input: string): string {
  const lines = input.split("\n");
  const out: string[] = [];
  for (let i = 0; i < lines.length; i += 1) {
    const line: string = lines[i] ?? "";
    const isOrdered = /^\s*\d+\.\s+/.test(line);
    const prev: string = out.length > 0 ? (out[out.length - 1] ?? "") : "";
    const prevBlank = out.length === 0 || prev.trim() === "";
    if (isOrdered && !prevBlank) {
      out.push("");
    }
    out.push(line);
  }
  return out.join("\n");
}

function processLatexContent(content: string): string {
  if (typeof content !== "string") return content;
  if (content.includes("$")) return content;

  let processed = content
    .replace(/^\s*\[\s*$/gm, "")
    .replace(/^\s*\]\s*$/gm, "")
    .replace(/\n\s*\n\s*\n/g, "\n\n");

  // Improve list detection: ensure blank line before ordered list markers
  processed = ensureListBlankLines(processed);

  const hasLatex = latexPatterns.some(p => p.test(processed));
  if (!hasLatex) return processed;

  // Protect math blocks if any existed (rare without delimiters). No-op here.

  // Inline auto-wrap: add $...$ around simple LaTeX occurrences
  processed = processed.replace(
    /(^|[\s.,!?;:])(\\(?:frac\{[^}]*\}\{[^}]*\}|sqrt\{[^}]*\}|[a-zA-Z]+))(?=[\s.,!?;:]|$)/g,
    (_unused, prefix, expr) => `${prefix}$${expr}$`
  );

  return processed;
}

export function Markdown({ children, className }: MarkdownProps) {
  const containsMath = useMemo(() => latexPatterns.some(p => p.test(children)), [children]);
  const processed = useMemo(() => processLatexContent(children), [children]);

  const markdownClassName = containsMath
    ? `markdown-no-prose max-w-none text-[var(--foreground)] ${className ?? ""}`
    : `max-w-none ${className ?? ""}`;

  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm, remarkMath]}
      rehypePlugins={[rehypeHighlight, rehypeKatex]}
      className={markdownClassName}
      components={{
        ol: ({ children, ...props }) => (
          <ol className="list-decimal ml-5 my-2 space-y-1" {...props}>
            {children}
          </ol>
        ),
        ul: ({ children, ...props }) => (
          <ul className="list-disc ml-5 my-2 space-y-1" {...props}>
            {children}
          </ul>
        ),
        li: ({ children, ...props }) => (
          <li className="leading-7" {...props}>
            {children}
          </li>
        ),
        p: ({ children, ...props }) => (
          <p className="my-3 leading-7 whitespace-pre-wrap break-words" {...props}>
            {children}
          </p>
        ),
        code: ({ children, className, ...props }) => (
          <code
            className={`bg-zinc-200 dark:bg-zinc-800 rounded px-1.5 py-0.5 ${className ?? ""}`}
            {...props}
          >
            {children}
          </code>
        ),
        pre: ({ children, ...props }) => (
          <pre
            className="rounded-lg !bg-zinc-900 !p-4 overflow-x-auto overflow-y-hidden border border-zinc-800 max-w-full"
            {...props}
          >
            {children}
          </pre>
        ),
        blockquote: ({ children, ...props }) => (
          <blockquote
            className="border-l-4 border-zinc-300 dark:border-zinc-700 pl-4 italic my-3"
            {...props}
          >
            {children}
          </blockquote>
        ),
        a: ({ children, ...props }) => (
          <a
            className="text-blue-600 dark:text-blue-400 hover:underline"
            target="_blank"
            rel="noopener noreferrer"
            {...props}
          >
            {children}
          </a>
        ),
        h1: ({ children, ...props }) => (
          <h1 className="block font-bold mt-4 mb-2 text-2xl" {...props}>
            {children}
          </h1>
        ),
        h2: ({ children, ...props }) => (
          <h2 className="block font-bold mt-4 mb-2 text-xl" {...props}>
            {children}
          </h2>
        ),
        h3: ({ children, ...props }) => (
          <h3 className="block font-bold mt-3 mb-2 text-lg" {...props}>
            {children}
          </h3>
        ),
        h4: ({ children, ...props }) => (
          <h4 className="block font-semibold mt-3 mb-1.5" {...props}>
            {children}
          </h4>
        ),
        h5: ({ children, ...props }) => (
          <h5 className="block font-medium mt-2.5 mb-1" {...props}>
            {children}
          </h5>
        ),
        h6: ({ children, ...props }) => (
          <h6 className="block font-medium mt-2 mb-1 text-sm" {...props}>
            {children}
          </h6>
        ),
        // eslint-disable-next-line @next/next/no-img-element, @typescript-eslint/no-explicit-any
        img: (props: any) => (
          <img
            {...props}
            alt={typeof props.alt === "string" ? props.alt : ""}
            className={`max-w-full w-full sm:max-w-[512px] rounded-lg border border-zinc-200 dark:border-zinc-700 ${props.className ?? ""}`}
            loading="lazy"
          />
        ),
      }}
    >
      {String(processed || "").replace(/\\n/g, "\n")}
    </ReactMarkdown>
  );
}

export default Markdown;
