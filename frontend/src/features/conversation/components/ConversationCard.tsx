"use client";

import React, { useMemo } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Components } from "react-markdown";
import { ExternalLink } from "lucide-react";

import type { Conversation } from "@/shared/lib/api-adapters";
import type { SearchResult as SearchHit } from "@/types";

interface SearchMatch {
  contentType: "conversation" | "imported_chat" | "draft_chat" | "project_draft";
  snippetMarkdown: string;
  query: string;
  score: number;
  createdAt: string;
  createdByUserName: string;
}

interface ConversationCardProps {
  conversation: Conversation;
  onSelect: (conversation: Conversation) => void;
  searchMatch?: SearchMatch | null;
  draftChatMatch?: SearchMatch | null;
  projectDraftMatch?: SearchMatch | null;
  importedChatMatch?: SearchMatch | null;
}

function getRelativeTime(dateIso: string): string {
  const date = new Date(dateIso);
  const diffMs = Date.now() - date.getTime();
  const absSec = Math.max(0, Math.floor(Math.abs(diffMs) / 1000));

  // Abbreviated units for compact display
  const units: [label: string, seconds: number][] = [
    ["y", 60 * 60 * 24 * 365],
    ["mo", 60 * 60 * 24 * 30],
    ["w", 60 * 60 * 24 * 7],
    ["d", 60 * 60 * 24],
    ["h", 60 * 60],
    ["m", 60],
    ["s", 1],
  ];

  for (const [label, seconds] of units) {
    const value = Math.floor(absSec / seconds);
    if (value >= 1) {
      return `${value}${label} ago`;
    }
  }
  return "now";
}

export function ConversationCard({
  conversation,
  onSelect,
  searchMatch,
  draftChatMatch,
  projectDraftMatch,
  importedChatMatch,
}: ConversationCardProps): React.JSX.Element {
  const updatedRel = useMemo(
    () => getRelativeTime(conversation.updatedAt),
    [conversation.updatedAt]
  );
  const importedRel = useMemo(
    () => getRelativeTime(conversation.importDate),
    [conversation.importDate]
  );
  const abstractPreview = (conversation.ideaAbstract ?? "").slice(0, 500);
  const lastUser = (conversation.lastUserMessageContent ?? "").slice(0, 120);
  const lastAssistant = (conversation.lastAssistantMessageContent ?? "").slice(0, 120);
  const isGrid = false;

  function escapeRegExp(input: string): string {
    return input.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  }

  function highlightInline(text: string, query: string): React.ReactNode[] {
    if (!query.trim()) return [text];
    try {
      const regex = new RegExp(`(${escapeRegExp(query)})`, "gi");
      const parts = text.split(regex);
      return parts.map((part, idx) => (idx % 2 === 1 ? <mark key={idx}>{part}</mark> : part));
    } catch {
      return [text];
    }
  }

  function mdComponents(query: string): Components {
    const withHighlight = (children: React.ReactNode): React.ReactNode =>
      React.Children.map(children, child =>
        typeof child === "string" ? highlightInline(child, query) : child
      );

    return {
      p: ({ children }) => <p className="text-sm text-foreground">{withHighlight(children)}</p>,
      li: ({ children }) => <li className="text-sm text-foreground">{withHighlight(children)}</li>,
    } as Components;
  }

  // Compute per-panel scores to color the highest one
  const effectiveChatScore =
    (searchMatch && searchMatch.contentType === "draft_chat"
      ? searchMatch.score
      : draftChatMatch?.score) ?? null;
  const effectiveProjectScore =
    (searchMatch && searchMatch.contentType === "project_draft"
      ? searchMatch.score
      : projectDraftMatch?.score) ?? null;
  const effectiveImportedScore =
    (searchMatch && searchMatch.contentType === "imported_chat"
      ? searchMatch.score
      : importedChatMatch?.score) ?? null;

  const scores = [effectiveChatScore, effectiveProjectScore, effectiveImportedScore].filter(
    (v): v is number => v !== null && v !== undefined
  );
  const maxScore = scores.length > 0 ? Math.max(...scores) : null;
  const isChatMax =
    maxScore !== null && effectiveChatScore !== null && effectiveChatScore === maxScore;
  const isProjectMax =
    maxScore !== null && effectiveProjectScore !== null && effectiveProjectScore === maxScore;
  const isImportedMax =
    maxScore !== null && effectiveImportedScore !== null && effectiveImportedScore === maxScore;

  const badgeClass = (isMax: boolean) =>
    `inline-flex items-center px-1.5 py-0.5 rounded ${isMax ? "bg-primary/20 text-primary" : "bg-muted text-muted-foreground"}`;

  return (
    <div
      className="group relative border border-border rounded-lg p-4 cursor-pointer transition-all shadow-sm hover:shadow-md bg-card hover:bg-muted"
      onClick={() => onSelect(conversation)}
    >
      <div className={"flex flex-col md:flex-row md:items-start md:gap-6"}>
        {/* Left: Title and meta */}
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2">
            <h3 className="text-base font-semibold text-foreground truncate">
              {searchMatch?.contentType === "conversation"
                ? highlightInline(conversation.title, searchMatch.query)
                : conversation.title}
            </h3>
          </div>

          {/* conversation match snippet moved to bottom full-width */}

          {/* Idea preview - always visible when present or when there's a match */}
          {(conversation.ideaTitle ||
            conversation.ideaAbstract ||
            projectDraftMatch ||
            (searchMatch && searchMatch.contentType === "project_draft")) && (
            <div className="mt-3 bg-muted/60 border border-border rounded p-3">
              <div className="flex items-center justify-between">
                <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                  Idea
                </h4>
                {(searchMatch?.contentType === "project_draft" || projectDraftMatch) && (
                  <span className={`ml-2 ${badgeClass(isProjectMax)} text-xs`}>
                    Score{" "}
                    {(
                      (searchMatch?.contentType === "project_draft"
                        ? searchMatch.score
                        : projectDraftMatch?.score) ?? 0
                    ).toFixed(2)}
                  </span>
                )}
              </div>
              {conversation.ideaTitle && (
                <p className="text-sm font-medium text-foreground mt-1 line-clamp-1">
                  {conversation.ideaTitle}
                </p>
              )}
              {(searchMatch && searchMatch.contentType === "project_draft") || projectDraftMatch ? (
                <div className="text-xs text-muted-foreground mt-1 line-clamp-4 prose prose-sm max-w-none">
                  <ReactMarkdown
                    remarkPlugins={[remarkGfm]}
                    components={mdComponents(
                      (searchMatch && searchMatch.contentType === "project_draft"
                        ? searchMatch.query
                        : projectDraftMatch?.query) || ""
                    )}
                  >
                    {(searchMatch && searchMatch.contentType === "project_draft"
                      ? searchMatch.snippetMarkdown
                      : projectDraftMatch?.snippetMarkdown) || ""}
                  </ReactMarkdown>
                </div>
              ) : (
                conversation.ideaAbstract && (
                  <p className="text-xs text-muted-foreground mt-1 line-clamp-4">
                    {abstractPreview}
                    {conversation.ideaAbstract.length > 500 ? "…" : ""}
                  </p>
                )
              )}
            </div>
          )}
        </div>

        {/* Right: Chat preview container (list view only) - always visible when it exists, or when chat_message matched */}
        {(lastUser ||
          lastAssistant ||
          (searchMatch && searchMatch.contentType === "draft_chat") ||
          draftChatMatch) && (
          <div className="mt-3 md:mt-0 md:w-1/2">
            <div className="rounded-lg border border-border bg-muted p-2 text-xs shadow-sm">
              <div className="flex items-center justify-between px-1 mb-1">
                <div className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wide">
                  Chat
                </div>
                {(searchMatch && searchMatch.contentType === "draft_chat") || draftChatMatch ? (
                  <div className="flex items-center gap-2 text-xs text-muted-foreground">
                    <span>
                      {new Date(
                        (searchMatch && searchMatch.contentType === "draft_chat"
                          ? searchMatch.createdAt
                          : draftChatMatch?.createdAt) || new Date().toISOString()
                      ).toLocaleDateString()}
                    </span>
                    <span className={badgeClass(isChatMax)}>
                      Score{" "}
                      {(
                        (searchMatch && searchMatch.contentType === "draft_chat"
                          ? searchMatch.score
                          : draftChatMatch?.score) ?? 0
                      ).toFixed(2)}
                    </span>
                  </div>
                ) : null}
              </div>
              <div className="space-y-2 px-1">
                {(searchMatch && searchMatch.contentType === "draft_chat") || draftChatMatch ? (
                  <div>
                    <div className="text-[11px] text-muted-foreground mb-0.5">Matched message</div>
                    <div className="inline-block rounded-2xl bg-card text-foreground px-3 py-1.5 leading-relaxed prose prose-sm max-w-none">
                      <ReactMarkdown
                        remarkPlugins={[remarkGfm]}
                        components={mdComponents(
                          (searchMatch && searchMatch.contentType === "draft_chat"
                            ? searchMatch.query
                            : draftChatMatch?.query) || ""
                        )}
                      >
                        {(searchMatch && searchMatch.contentType === "draft_chat"
                          ? searchMatch.snippetMarkdown
                          : draftChatMatch?.snippetMarkdown) || ""}
                      </ReactMarkdown>
                    </div>
                  </div>
                ) : (
                  <>
                    {lastUser && (
                      <div>
                        <div className="text-[11px] text-muted-foreground mb-0.5">
                          {conversation.userName}
                        </div>
                        <div className="inline-block max-w-full rounded-2xl bg-primary/10 text-primary px-3 py-1.5 leading-relaxed line-clamp-2">
                          {lastUser}
                          {(conversation.lastUserMessageContent?.length ?? 0) > 120 ? "…" : ""}
                        </div>
                      </div>
                    )}
                    {lastAssistant && (
                      <div>
                        <div className="text-[11px] text-muted-foreground mb-0.5">Assistant</div>
                        <div className="inline-block max-w-full rounded-2xl bg-card text-foreground px-3 py-1.5 leading-relaxed line-clamp-2">
                          {lastAssistant}
                          {(conversation.lastAssistantMessageContent?.length ?? 0) > 120 ? "…" : ""}
                        </div>
                      </div>
                    )}
                  </>
                )}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Bottom full-width: Imported Chat panel */}
      {(searchMatch?.contentType === "imported_chat" || importedChatMatch) && (
        <div className="mt-4 bg-muted/60 border border-border rounded p-3">
          <div className="flex items-center justify-between mb-1">
            <span className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
              Imported Chat
            </span>
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <span className={badgeClass(isImportedMax)}>
                Score{" "}
                {(
                  (searchMatch?.contentType === "imported_chat"
                    ? searchMatch.score
                    : importedChatMatch?.score) ?? 0
                ).toFixed(2)}
              </span>
            </div>
          </div>
          {searchMatch?.contentType === "imported_chat" && (
            <>
              <div className="text-sm text-foreground prose prose-sm max-w-none">
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  components={mdComponents(searchMatch.query)}
                >
                  {searchMatch.snippetMarkdown}
                </ReactMarkdown>
              </div>
              <div className="mt-1 text-xs text-muted-foreground">
                {searchMatch.createdByUserName}
              </div>
            </>
          )}
          {searchMatch?.contentType !== "imported_chat" && importedChatMatch && (
            <>
              <div className="text-sm text-foreground prose prose-sm max-w-none">
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  components={mdComponents(importedChatMatch.query)}
                >
                  {importedChatMatch.snippetMarkdown}
                </ReactMarkdown>
              </div>
              <div className="mt-1 text-xs text-muted-foreground">
                {importedChatMatch.createdByUserName}
              </div>
            </>
          )}
        </div>
      )}

      {/* Footer meta */}
      <div className="mt-4 flex items-center justify-between text-xs text-muted-foreground gap-2">
        <div className="flex items-center gap-2 flex-nowrap">
          <a
            href={conversation.url}
            target="_blank"
            rel="noreferrer"
            onClick={e => e.stopPropagation()}
            className="inline-flex items-center gap-1 text-muted-foreground hover:text-foreground"
            title="Open imported chat"
          >
            <ExternalLink className="w-3.5 h-3.5" />
            {!isGrid && <span>Imported Chat</span>}
          </a>
        </div>
        <div className="flex items-center gap-3 whitespace-nowrap">
          <span title={new Date(conversation.updatedAt).toISOString()}>Updated {updatedRel}</span>
          <span
            className="text-muted-foreground/60"
            title={new Date(conversation.importDate).toISOString()}
          >
            Imported {importedRel}
          </span>
        </div>
      </div>
    </div>
  );
}

export function toSearchMatchFromHit(hit: SearchHit, query: string): SearchMatch {
  return {
    contentType: hit.content_type as SearchMatch["contentType"],
    snippetMarkdown: hit.content_snippet,
    query,
    score: hit.score,
    createdAt: hit.created_at,
    createdByUserName: hit.created_by_user_name,
  };
}
