"use client";

import { useState } from "react";
import { ChevronDown, Download, FileText, Trophy } from "lucide-react";
import { cn } from "@/shared/lib/utils";
import { api } from "@/shared/lib/api-client-typed";

// Scores from the best paper analysis
const SCORES = [
  { label: "Originality", value: 3, max: 4 },
  { label: "Quality", value: 3, max: 4 },
  { label: "Clarity", value: 3, max: 4 },
  { label: "Significance", value: 3, max: 4 },
  { label: "Soundness", value: 3, max: 4 },
  { label: "Presentation", value: 3, max: 4 },
  { label: "Contribution", value: 3, max: 4 },
  { label: "Overall", value: 6, max: 10 },
  { label: "Confidence", value: 3, max: 5 },
];

const SUMMARY = `The paper studies a controlled "token forgetting" phenomenon in sequential fine-tuning when checkpoint selection is driven only by the current objective. Using distilgpt2, Stage 1 "installs" 8 synthetic strings that each map to a single new token id, reaching perfect held-out next-token accuracy on carrier prompts. Stage 2 fine-tunes on WikiText-2 while excluding these installed tokens and selects the checkpoint solely by minimum Stage-2 validation loss; retention is evaluated only after this selection and drops substantially (reported 1.0 → 0.479 micro accuracy in the main run). The core scientific question is where forgetting lives causally: in the readout pathway ("head": final layer norm LN_f and unembedding W_U) versus in upper-layer residual-stream features ("body") and their alignment with the head.`;

const STRENGTHS = [
  "Clear, deployment-motivated setup: Stage-2 checkpoint selection ignores retention, matching realistic pipelines where earlier capabilities are out-of-objective and thus can silently degrade.",
  "Causal localization is the main novelty: module swaps and targeted rollbacks manipulate disjoint parameter groups to adjudicate \"head drift\" vs \"feature drift\" more directly than representation-similarity diagnostics alone.",
  "Converging evidence in the main run: head rollback provides only modest retention recovery (~0.50) whereas body rollback restores perfect retention (1.0) but destroys Stage-2 loss.",
  "The paper connects diagnostics to interventions: the logit-drift decomposition reports the feature term dominating the head term by >10×.",
  "Includes several ablations probing training/selection knobs (weight decay sweep; optimizer moment carryover; freezing strategies; checkpoint selection criteria).",
];

const WEAKNESSES = [
  "Robustness is limited: the paper appears to rely heavily on single-seed point estimates for key causal claims.",
  "External validity remains uncertain: the core evidence is for synthetic single-token strings with carrier prompts on a small model (distilgpt2).",
  "The \"head\" grouping conflates LN_f and W_U; the causal attribution within the head is less sharp.",
  "Reproducibility signals are mixed: the submission does not clearly provide a public code/data link in the provided text.",
];

interface Section {
  id: string;
  title: string;
  content: React.ReactNode;
  defaultExpanded: boolean;
  color: "emerald" | "amber" | "sky";
}

interface BestPaperShowcaseProps {
  className?: string;
}

export function BestPaperShowcase({ className }: BestPaperShowcaseProps) {
  const [expandedSections, setExpandedSections] = useState<Record<string, boolean>>({
    summary: true,
    strengths: false,
    weaknesses: false,
  });
  const [isDownloading, setIsDownloading] = useState(false);
  const [downloadError, setDownloadError] = useState<string | null>(null);

  const toggleSection = (sectionId: string) => {
    setExpandedSections(prev => ({
      ...prev,
      [sectionId]: !prev[sectionId],
    }));
  };

  const handleDownload = async () => {
    setIsDownloading(true);
    setDownloadError(null);
    try {
      const { data, error } = await api.GET("/api/public-config/best-paper-url");
      if (error || !data?.download_url) {
        throw new Error("Failed to get download URL");
      }
      window.open(data.download_url, "_blank");
    } catch (error) {
      setDownloadError("Failed to download paper. Please try again.");
      console.error("Download error:", error);
    } finally {
      setIsDownloading(false);
    }
  };

  const bulletColor = (color: string) => {
    const colors: Record<string, string> = {
      emerald: "text-emerald-400 marker:text-emerald-400",
      amber: "text-amber-400 marker:text-amber-400",
      sky: "text-sky-400 marker:text-sky-400",
    };
    return colors[color] || "";
  };

  const sections: Section[] = [
    {
      id: "summary",
      title: "Summary",
      content: <p className="text-slate-300 whitespace-pre-wrap">{SUMMARY}</p>,
      defaultExpanded: true,
      color: "sky",
    },
    {
      id: "strengths",
      title: "Strengths",
      content: (
        <ul className={cn("list-disc list-inside space-y-2", bulletColor("emerald"))}>
          {STRENGTHS.map((strength, idx) => (
            <li key={idx} className="text-slate-300">
              {strength}
            </li>
          ))}
        </ul>
      ),
      defaultExpanded: false,
      color: "emerald",
    },
    {
      id: "weaknesses",
      title: "Weaknesses",
      content: (
        <ul className={cn("list-disc list-inside space-y-2", bulletColor("amber"))}>
          {WEAKNESSES.map((weakness, idx) => (
            <li key={idx} className="text-slate-300">
              {weakness}
            </li>
          ))}
        </ul>
      ),
      defaultExpanded: false,
      color: "amber",
    },
  ];

  return (
    <div className={cn("space-y-4", className)}>
      {/* Header */}
      <div className="flex items-center gap-2 text-xs uppercase tracking-[0.2em] text-slate-400">
        <Trophy className="h-4 w-4 text-amber-400" />
        <span>Example Output</span>
      </div>
      <h3 className="text-lg font-semibold text-white">Best Paper Produced</h3>
      <p className="text-slate-300 text-sm">
        See what AE Scientist can produce. This paper received an &quot;Accept&quot; decision from our
        automated peer review system with an overall score of 6/10.
      </p>

      {/* Scores Grid */}
      <div className="grid grid-cols-3 gap-2">
        {SCORES.map(metric => (
          <div
            key={metric.label}
            className="rounded-lg border border-slate-800/60 bg-slate-900/40 p-3"
          >
            <div className="text-xs text-slate-400 uppercase tracking-wide mb-1">{metric.label}</div>
            <div className="text-lg font-bold text-amber-300">
              {metric.value}
              <span className="text-sm text-slate-500 font-normal">/{metric.max}</span>
            </div>
          </div>
        ))}
      </div>

      {/* Analysis Sections */}
      <div className="space-y-0 border border-slate-800/60 rounded-lg overflow-hidden">
        {sections.map((section, idx) => (
          <div
            key={section.id}
            className={cn(idx !== sections.length - 1 && "border-b border-slate-800/60")}
          >
            <button
              onClick={() => toggleSection(section.id)}
              className="flex items-center justify-between w-full py-3 px-4 text-left hover:bg-slate-800/30 transition"
            >
              <span className="font-medium text-white">{section.title}</span>
              <ChevronDown
                className={cn(
                  "h-4 w-4 text-slate-400 transition-transform",
                  expandedSections[section.id] && "rotate-180"
                )}
              />
            </button>

            {expandedSections[section.id] && (
              <div className="px-4 pb-3 text-sm">{section.content}</div>
            )}
          </div>
        ))}
      </div>

      {/* Download Banner */}
      <div className="rounded-lg border border-violet-800/60 bg-gradient-to-r from-violet-950/50 to-violet-900/30 p-4">
        <div className="flex items-center justify-between">
          <div className="flex items-start gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-violet-500/20">
              <FileText className="h-5 w-5 text-violet-400" />
            </div>
            <div>
              <h4 className="text-sm font-semibold text-violet-100">Download Full Paper</h4>
              <p className="text-xs text-violet-300/80 mt-0.5">
                View the complete research paper with all figures and analysis
              </p>
            </div>
          </div>
          <button
            onClick={handleDownload}
            disabled={isDownloading}
            className="flex items-center justify-center gap-2 rounded border border-violet-600 bg-violet-500/20 px-4 py-2 text-sm font-medium text-violet-100 transition-colors hover:bg-violet-500/30 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isDownloading ? (
              <>
                <div className="h-4 w-4 animate-pulse">...</div>
                <span>Loading...</span>
              </>
            ) : (
              <>
                <Download className="h-4 w-4" />
                <span>Download PDF</span>
              </>
            )}
          </button>
        </div>
        {downloadError && (
          <div className="mt-2 text-xs text-red-400">{downloadError}</div>
        )}
      </div>
    </div>
  );
}
