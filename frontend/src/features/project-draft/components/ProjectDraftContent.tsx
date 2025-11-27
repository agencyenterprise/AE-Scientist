import React from "react";
import ReactMarkdown from "react-markdown";
import type { Idea } from "@/types";
import { isIdeaGenerating } from "../utils/versionUtils";

interface ProjectDraftContentProps {
  projectDraft: Idea;
  isEditing: boolean;
  editDescription: string;
  setEditDescription: (description: string) => void;
  onKeyDown: (event: React.KeyboardEvent, action: () => void) => void;
  onSave: () => Promise<void>;
  onCancelEdit: () => void;
}

export function ProjectDraftContent({
  projectDraft,
  isEditing,
  editDescription,
  setEditDescription,
  onKeyDown,
  onSave,
  onCancelEdit,
}: ProjectDraftContentProps): React.JSX.Element {
  const isGenerating = isIdeaGenerating(projectDraft);
  const activeVersion = projectDraft.active_version;

  /* eslint-disable @typescript-eslint/no-explicit-any */
  const markdownComponents: any = {
    h1: (props: any) => (
      <h1 className="text-lg font-bold mb-2 mt-3 first:mt-0">{props.children}</h1>
    ),
    h2: (props: any) => (
      <h2 className="text-base font-semibold mb-1 mt-2 first:mt-0">{props.children}</h2>
    ),
    h3: (props: any) => (
      <h3 className="text-base font-medium mb-1 mt-2 first:mt-0">{props.children}</h3>
    ),
    p: (props: any) => <p className="mb-1 last:mb-0">{props.children}</p>,
    ul: (props: any) => <ul className="list-disc ml-4 mb-1 space-y-0.5">{props.children}</ul>,
    ol: (props: any) => <ol className="list-decimal ml-4 mb-1 space-y-0.5">{props.children}</ol>,
    li: (props: any) => <li>{props.children}</li>,
    code: (props: any) => (
      <code className="bg-muted px-1 py-0.5 rounded text-xs font-mono">{props.children}</code>
    ),
    pre: (props: any) => (
      <pre className="bg-muted p-2 rounded text-xs font-mono overflow-x-auto mb-1">
        {props.children}
      </pre>
    ),
    strong: (props: any) => <strong className="font-semibold">{props.children}</strong>,
    em: (props: any) => <em className="italic">{props.children}</em>,
    a: (props: any) => (
      <a
        href={props.href}
        className="text-primary hover:underline"
        target="_blank"
        rel="noopener noreferrer"
      >
        {props.children}
      </a>
    ),
  };
  /* eslint-enable @typescript-eslint/no-explicit-any */

  if (isEditing) {
    return (
      <div className="flex-1 flex flex-col min-h-0">
        <div className="flex items-center justify-between mb-2">
          <label className="text-sm font-medium text-muted-foreground">
            Edit Idea (JSON format required)
          </label>
        </div>
        <div className="flex-1 flex flex-col min-h-0">
          <textarea
            value={editDescription}
            onChange={e => setEditDescription(e.target.value)}
            onKeyDown={e => onKeyDown(e, onSave)}
            className="input-field flex-1 min-h-[45vh] sm:min-h-[20rem] resize-none overflow-auto font-mono"
            placeholder="Enter idea data as JSON..."
          />
          <div className="flex justify-end space-x-2 mt-2">
            <button onClick={onCancelEdit} className="btn-secondary text-xs py-1">
              Cancel
            </button>
            <button onClick={onSave} className="btn-primary-gradient text-xs py-1 px-3">
              Save
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col min-h-0 overflow-hidden">
      <div className="flex-1 overflow-y-auto px-1 space-y-6">
        {isGenerating ? (
          <div className="space-y-4">
            <div className="animate-pulse space-y-2">
              <div className="h-3 bg-primary/30 rounded w-full"></div>
              <div className="h-3 bg-primary/30 rounded w-5/6"></div>
              <div className="h-3 bg-primary/30 rounded w-4/5"></div>
              <div className="h-3 bg-primary/30 rounded w-3/4"></div>
            </div>
          </div>
        ) : (
          <>
            {/* Short Hypothesis */}
            {activeVersion?.short_hypothesis && (
              <div className="border-l-4 border-primary pl-4">
                <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-1">
                  Hypothesis
                </h3>
                <div className="text-sm text-foreground leading-relaxed">
                  <ReactMarkdown components={markdownComponents}>
                    {activeVersion.short_hypothesis}
                  </ReactMarkdown>
                </div>
              </div>
            )}

            {/* Related Work */}
            {activeVersion?.related_work && (
              <div>
                <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">
                  Related Work
                </h3>
                <div className="text-sm text-foreground/90 leading-relaxed">
                  <ReactMarkdown components={markdownComponents}>
                    {activeVersion.related_work}
                  </ReactMarkdown>
                </div>
              </div>
            )}

            {/* Abstract */}
            {activeVersion?.abstract && (
              <div>
                <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">
                  Abstract
                </h3>
                <div className="text-sm text-foreground/90 leading-relaxed">
                  <ReactMarkdown components={markdownComponents}>
                    {activeVersion.abstract}
                  </ReactMarkdown>
                </div>
              </div>
            )}

            {/* Experiments - styled like orchestrator's Hypothesis History */}
            {activeVersion?.experiments && activeVersion.experiments.length > 0 && (
              <div>
                <h3 className="text-xs font-semibold text-primary uppercase tracking-widest mb-4">
                  Experiments
                </h3>
                <div className="space-y-3">
                  {activeVersion.experiments.map((experiment, idx) => (
                    <article
                      key={idx}
                      className="group overflow-hidden rounded-xl border border-border bg-muted/50 p-4 transition hover:border-primary/40"
                    >
                      <div className="flex items-start gap-3">
                        <span className="inline-flex items-center justify-center w-7 h-7 rounded-full bg-primary text-primary-foreground text-xs font-bold flex-shrink-0 shadow-sm">
                          {idx + 1}
                        </span>
                        <div className="flex-1 text-sm text-foreground leading-relaxed">
                          <ReactMarkdown components={markdownComponents}>
                            {experiment}
                          </ReactMarkdown>
                        </div>
                      </div>
                    </article>
                  ))}
                </div>
              </div>
            )}

            {/* Expected Outcome */}
            {activeVersion?.expected_outcome && (
              <div>
                <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">
                  Expected Outcome
                </h3>
                <div className="text-sm text-foreground bg-green-500/10 border border-green-500/30 rounded-xl p-4 leading-relaxed">
                  <ReactMarkdown components={markdownComponents}>
                    {activeVersion.expected_outcome}
                  </ReactMarkdown>
                </div>
              </div>
            )}

            {/* Risk Factors and Limitations */}
            {activeVersion?.risk_factors_and_limitations &&
              activeVersion.risk_factors_and_limitations.length > 0 && (
                <div>
                  <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">
                    Risk Factors & Limitations
                  </h3>
                  <div className="space-y-2">
                    {activeVersion.risk_factors_and_limitations.map((risk, idx) => (
                      <div
                        key={idx}
                        className="bg-amber-500/10 border border-amber-500/30 rounded-xl p-4"
                      >
                        <div className="flex items-start gap-3">
                          <svg
                            className="w-5 h-5 text-amber-400 flex-shrink-0 mt-0.5"
                            fill="none"
                            stroke="currentColor"
                            viewBox="0 0 24 24"
                          >
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              strokeWidth={2}
                              d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
                            />
                          </svg>
                          <div className="flex-1 text-sm text-foreground leading-relaxed">
                            <ReactMarkdown components={markdownComponents}>{risk}</ReactMarkdown>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
          </>
        )}
      </div>
    </div>
  );
}
