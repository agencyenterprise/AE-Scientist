"use client";

import { useState } from "react";
import {
  ThumbsUp,
  ThumbsDown,
  HelpCircle,
  AlertTriangle,
  CheckCircle,
  XCircle,
  ChevronDown,
  ChevronUp,
  Download,
  Loader2,
  Eye,
  Search,
  BookOpen,
  FileWarning,
  Layout,
  ExternalLink,
} from "lucide-react";
import { config } from "@/shared/lib/config";
import { withAuthHeaders } from "@/shared/lib/session-token";
import type { AnyPaperReviewDetail } from "@/features/paper-review/api";

export type { AnyPaperReviewDetail };

interface PaperReviewResultProps {
  data: AnyPaperReviewDetail;
}

interface ScoreMetric {
  label: string;
  key: string;
  max: number;
}

const NEURIPS_METRICS: ScoreMetric[] = [
  { label: "Quality", key: "quality", max: 4 },
  { label: "Clarity", key: "clarity", max: 4 },
  { label: "Significance", key: "significance", max: 4 },
  { label: "Originality", key: "originality", max: 4 },
  { label: "Overall", key: "overall", max: 6 },
  { label: "Confidence", key: "confidence", max: 5 },
];

const ICLR_METRICS: ScoreMetric[] = [
  { label: "Soundness", key: "soundness", max: 4 },
  { label: "Presentation", key: "presentation", max: 4 },
  { label: "Contribution", key: "contribution", max: 4 },
  { label: "Overall", key: "overall", max: 10 },
  { label: "Confidence", key: "confidence", max: 5 },
];

const ICML_METRICS: ScoreMetric[] = [{ label: "Overall", key: "overall", max: 5 }];

function getMetricsForConference(conference: string): ScoreMetric[] {
  if (conference === "neurips_2025") return NEURIPS_METRICS;
  if (conference === "iclr_2025") return ICLR_METRICS;
  return ICML_METRICS;
}

function getOverallMax(conference: string): number {
  if (conference === "neurips_2025") return 6;
  if (conference === "icml") return 5;
  return 10;
}

const LABELS_POOR_TO_EXCELLENT: Record<number, string> = {
  1: "Poor",
  2: "Fair",
  3: "Good",
  4: "Excellent",
};

const LABELS_NEURIPS_OVERALL: Record<number, string> = {
  1: "Strong Reject",
  2: "Reject",
  3: "Borderline Reject",
  4: "Borderline Accept",
  5: "Accept",
  6: "Strong Accept",
};

const LABELS_ICLR_OVERALL: Record<number, string> = {
  1: "Very Strong Reject",
  3: "Reject",
  5: "Borderline Reject",
  6: "Borderline Accept",
  8: "Accept",
  10: "Strong Accept",
};

const LABELS_ICML_OVERALL: Record<number, string> = {
  1: "Reject",
  2: "Weak Reject",
  3: "Weak Accept",
  4: "Accept",
  5: "Strong Accept",
};

const LABELS_CONFIDENCE: Record<number, string> = {
  1: "Educated guess",
  2: "Uncertain",
  3: "Fairly confident",
  4: "Confident",
  5: "Absolutely certain",
};

function getScoreLabel(key: string, score: number, conference: string): string {
  switch (key) {
    case "originality":
    case "quality":
    case "clarity":
    case "significance":
    case "soundness":
    case "presentation":
    case "contribution":
      return LABELS_POOR_TO_EXCELLENT[score] || "";
    case "overall":
      if (conference === "neurips_2025") return LABELS_NEURIPS_OVERALL[score] || "";
      if (conference === "iclr_2025") return LABELS_ICLR_OVERALL[score] || "";
      if (conference === "icml") return LABELS_ICML_OVERALL[score] || "";
      return "";
    case "confidence":
      return LABELS_CONFIDENCE[score] || "";
    default:
      return "";
  }
}

function getDecisionColor(decision: string): string {
  const d = decision.toLowerCase();
  if (d.includes("accept")) return "text-emerald-400 bg-emerald-500/10 border-emerald-500/30";
  if (d.includes("reject")) return "text-red-400 bg-red-500/10 border-red-500/30";
  return "text-amber-400 bg-amber-500/10 border-amber-500/30";
}

function getDecisionIcon(decision: string) {
  const d = decision.toLowerCase();
  if (d.includes("accept")) return <CheckCircle className="h-5 w-5" />;
  if (d.includes("reject")) return <XCircle className="h-5 w-5" />;
  return <HelpCircle className="h-5 w-5" />;
}

function getScoreColor(score: number, max: number): string {
  const ratio = score / max;
  if (ratio >= 0.75) return "text-emerald-400";
  if (ratio >= 0.5) return "text-amber-400";
  return "text-red-400";
}

function CollapsibleSection({
  title,
  icon,
  children,
  defaultOpen = true,
}: {
  title: string;
  icon: React.ReactNode;
  children: React.ReactNode;
  defaultOpen?: boolean;
}) {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  return (
    <div className="rounded-lg border border-slate-700 bg-slate-800/50">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex w-full items-center justify-between p-3 text-left sm:p-4"
      >
        <div className="flex items-center gap-2">
          {icon}
          <span className="text-sm font-medium text-white sm:text-base">{title}</span>
        </div>
        {isOpen ? (
          <ChevronUp className="h-5 w-5 shrink-0 text-slate-400" />
        ) : (
          <ChevronDown className="h-5 w-5 shrink-0 text-slate-400" />
        )}
      </button>
      {isOpen && <div className="border-t border-slate-700 p-3 sm:p-4">{children}</div>}
    </div>
  );
}

export function PaperReviewResult({ data }: PaperReviewResultProps) {
  const [isDownloading, setIsDownloading] = useState(false);
  const conference = data.conference;
  const overallMax = getOverallMax(conference);
  const scoreMetrics = getMetricsForConference(conference);
  const decision = data.decision || "";
  const overall = data.overall;

  const handleDownload = async () => {
    setIsDownloading(true);
    try {
      const headers = withAuthHeaders(new Headers());
      const response = await fetch(`${config.apiUrl}/paper-reviews/${data.id}/download`, {
        headers,
        credentials: "include",
      });

      if (!response.ok) {
        return;
      }

      const downloadData = await response.json();
      window.open(downloadData.download_url, "_blank");
    } finally {
      setIsDownloading(false);
    }
  };

  return (
    <div className="space-y-4 sm:space-y-6">
      {/* Decision Banner */}
      <div
        className={`flex flex-col gap-3 rounded-lg border p-3 sm:flex-row sm:items-center sm:justify-between sm:p-4 ${getDecisionColor(decision)}`}
      >
        <div className="flex items-center gap-3">
          {getDecisionIcon(decision)}
          <div>
            <div className="flex items-center gap-2">
              <span className="font-semibold">{decision}</span>
              {overall != null && overall > 0 && (
                <>
                  <span className="opacity-50">·</span>
                  <span className="text-lg font-bold">
                    {overall}/{overallMax}
                  </span>
                  <span className="text-sm opacity-70">
                    ({getScoreLabel("overall", overall, conference)})
                  </span>
                </>
              )}
            </div>
            <div className="text-sm opacity-80">
              Cost: ${((data.cost_cents ?? 0) / 100).toFixed(2)}
            </div>
          </div>
        </div>
        <button
          onClick={handleDownload}
          disabled={isDownloading}
          className="flex w-full items-center justify-center gap-2 rounded-lg border border-current px-3 py-1.5 text-sm transition-opacity hover:opacity-80 disabled:opacity-50 sm:w-auto"
          title="Download original paper"
        >
          {isDownloading ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Download className="h-4 w-4" />
          )}
          <span>Download PDF</span>
        </button>
      </div>

      {/* Summary */}
      {data.summary && (
        <div className="rounded-lg border border-slate-700 bg-slate-800/50 p-3 sm:p-4">
          <h3 className="mb-2 font-medium text-white sm:mb-3">Summary</h3>
          <p className="text-sm leading-relaxed text-slate-300">{data.summary}</p>
        </div>
      )}

      {/* Scores Grid */}
      <div>
        <h3 className="mb-2 font-medium text-white sm:mb-3">Quantitative Scores</h3>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 sm:gap-3 lg:grid-cols-5">
          {scoreMetrics.map(metric => {
            const score = (data as Record<string, unknown>)[metric.key] as
              | number
              | null
              | undefined;
            if (score == null) return null;
            const label = getScoreLabel(metric.key, score, conference);
            return (
              <div
                key={metric.label}
                className="rounded-lg border border-slate-700 bg-slate-800/50 p-2 text-center sm:p-3"
              >
                <div className="mb-1 text-[10px] text-slate-400 sm:text-xs">{metric.label}</div>
                <div className={`text-lg font-bold sm:text-xl ${getScoreColor(score, metric.max)}`}>
                  {score}
                  <span className="text-xs font-normal text-slate-500 sm:text-sm">
                    /{metric.max}
                  </span>
                </div>
                {label && (
                  <div className="mt-1 hidden text-xs text-slate-500 sm:block">{label}</div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* NeurIPS: combined Strengths & Weaknesses */}
      {data.conference === "neurips_2025" && data.strengths_and_weaknesses && (
        <CollapsibleSection
          title="Strengths & Weaknesses"
          icon={<ThumbsUp className="h-5 w-5 text-emerald-400" />}
        >
          <p className="text-sm leading-relaxed text-slate-300">{data.strengths_and_weaknesses}</p>
        </CollapsibleSection>
      )}

      {/* ICLR: separate Strengths and Weaknesses */}
      {data.conference === "iclr_2025" && (
        <>
          {data.strengths && data.strengths.length > 0 && (
            <CollapsibleSection
              title={`Strengths (${data.strengths.length})`}
              icon={<ThumbsUp className="h-5 w-5 text-emerald-400" />}
            >
              <ul className="space-y-2">
                {data.strengths.map((strength, i) => (
                  <li key={i} className="flex gap-2 text-sm text-slate-300">
                    <span className="mt-1.5 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-emerald-400" />
                    {strength}
                  </li>
                ))}
              </ul>
            </CollapsibleSection>
          )}
          {data.weaknesses && data.weaknesses.length > 0 && (
            <CollapsibleSection
              title={`Weaknesses (${data.weaknesses.length})`}
              icon={<ThumbsDown className="h-5 w-5 text-red-400" />}
            >
              <ul className="space-y-2">
                {data.weaknesses.map((weakness, i) => (
                  <li key={i} className="flex gap-2 text-sm text-slate-300">
                    <span className="mt-1.5 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-red-400" />
                    {weakness}
                  </li>
                ))}
              </ul>
            </CollapsibleSection>
          )}
        </>
      )}

      {/* ICML: claims, prior work, other aspects */}
      {data.conference === "icml" && (
        <>
          {data.claims_and_evidence && (
            <CollapsibleSection
              title="Claims & Evidence"
              icon={<CheckCircle className="h-5 w-5 text-emerald-400" />}
            >
              <p className="text-sm leading-relaxed text-slate-300">{data.claims_and_evidence}</p>
            </CollapsibleSection>
          )}
          {data.relation_to_prior_work && (
            <CollapsibleSection
              title="Relation to Prior Work"
              icon={<HelpCircle className="h-5 w-5 text-sky-400" />}
            >
              <p className="text-sm leading-relaxed text-slate-300">
                {data.relation_to_prior_work}
              </p>
            </CollapsibleSection>
          )}
          {data.other_aspects && (
            <CollapsibleSection
              title="Other Aspects"
              icon={<AlertTriangle className="h-5 w-5 text-amber-400" />}
            >
              <p className="text-sm leading-relaxed text-slate-300">{data.other_aspects}</p>
            </CollapsibleSection>
          )}
        </>
      )}

      {/* Questions (ICLR and ICML) */}
      {(data.conference === "iclr_2025" || data.conference === "icml") &&
        data.questions &&
        data.questions.length > 0 && (
          <CollapsibleSection
            title={`Questions (${data.questions.length})`}
            icon={<HelpCircle className="h-5 w-5 text-sky-400" />}
            defaultOpen={false}
          >
            <ul className="space-y-2">
              {data.questions.map((question, i) => (
                <li key={i} className="flex gap-2 text-sm text-slate-300">
                  <span className="mt-1.5 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-sky-400" />
                  {question}
                </li>
              ))}
            </ul>
          </CollapsibleSection>
        )}

      {/* Limitations (NeurIPS and ICLR) */}
      {(data.conference === "neurips_2025" || data.conference === "iclr_2025") &&
        data.limitations && (
          <CollapsibleSection
            title="Limitations"
            icon={<AlertTriangle className="h-5 w-5 text-amber-400" />}
            defaultOpen={false}
          >
            <p className="text-sm leading-relaxed text-slate-300">{data.limitations}</p>
          </CollapsibleSection>
        )}

      {/* Clarity Issues (all conferences) */}
      {data.clarity_issues && data.clarity_issues.length > 0 && (
        <CollapsibleSection
          title={`Clarity Issues (${data.clarity_issues.length})`}
          icon={<Eye className="h-5 w-5 text-violet-400" />}
          defaultOpen={false}
        >
          <ul className="space-y-3">
            {data.clarity_issues.map((item, i) => (
              <li key={i} className="text-sm text-slate-300">
                <span className="font-medium text-violet-400">{item.location}:</span> {item.issue}
              </li>
            ))}
          </ul>
        </CollapsibleSection>
      )}

      {/* Novelty Search Results */}
      {data.novelty_search && (
        <CollapsibleSection
          title={`Novelty Search (${data.novelty_search.results.length} results)`}
          icon={<Search className="h-5 w-5 text-sky-400" />}
          defaultOpen={false}
        >
          <div className="space-y-3">
            <p className="text-sm leading-relaxed text-slate-300">{data.novelty_search.summary}</p>
            {data.novelty_search.results.length > 0 && (
              <ul className="space-y-2">
                {data.novelty_search.results.map((result, i) => (
                  <li
                    key={i}
                    className="rounded border border-slate-700 bg-slate-800/80 p-2 text-sm"
                  >
                    <a
                      href={result.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center gap-1 font-medium text-sky-400 hover:text-sky-300"
                    >
                      {result.title}
                      <ExternalLink className="h-3 w-3 flex-shrink-0" />
                    </a>
                    <p className="mt-1 text-slate-400">{result.snippet}</p>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </CollapsibleSection>
      )}

      {/* Citation Check Results */}
      {data.citation_check && data.citation_check.checks.length > 0 && (
        <CollapsibleSection
          title={`Citation Check (${data.citation_check.checks.length} citations)`}
          icon={<BookOpen className="h-5 w-5 text-amber-400" />}
          defaultOpen={false}
        >
          <div className="space-y-3">
            <p className="text-sm leading-relaxed text-slate-300">{data.citation_check.summary}</p>
            <ul className="space-y-2">
              {data.citation_check.checks.map((check, i) => (
                <li key={i} className="rounded border border-slate-700 bg-slate-800/80 p-2 text-sm">
                  <div className="flex items-start gap-2">
                    {check.found ? (
                      <CheckCircle className="mt-0.5 h-4 w-4 flex-shrink-0 text-emerald-400" />
                    ) : (
                      <XCircle className="mt-0.5 h-4 w-4 flex-shrink-0 text-red-400" />
                    )}
                    <div>
                      <p className="text-slate-300">{check.cited_text}</p>
                      <p className="mt-1 text-slate-400">{check.assessment}</p>
                      {check.found && check.url && (
                        <a
                          href={check.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="mt-1 inline-flex items-center gap-1 text-sky-400 hover:text-sky-300"
                        >
                          Source <ExternalLink className="h-3 w-3" />
                        </a>
                      )}
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        </CollapsibleSection>
      )}

      {/* Missing References Results */}
      {data.missing_references && data.missing_references.missing_references.length > 0 && (
        <CollapsibleSection
          title={`Missing References (${data.missing_references.missing_references.length})`}
          icon={<FileWarning className="h-5 w-5 text-orange-400" />}
          defaultOpen={false}
        >
          <div className="space-y-3">
            <p className="text-sm leading-relaxed text-slate-300">
              {data.missing_references.summary}
            </p>
            <ul className="space-y-2">
              {data.missing_references.missing_references.map((ref, i) => (
                <li key={i} className="rounded border border-slate-700 bg-slate-800/80 p-2 text-sm">
                  <div className="flex items-center gap-1">
                    <span className="font-medium text-orange-400">{ref.topic}</span>
                  </div>
                  <a
                    href={ref.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="mt-1 inline-flex items-center gap-1 text-sky-400 hover:text-sky-300"
                  >
                    {ref.missing_work} <ExternalLink className="h-3 w-3" />
                  </a>
                  <p className="mt-1 text-slate-400">{ref.relevance}</p>
                </li>
              ))}
            </ul>
          </div>
        </CollapsibleSection>
      )}

      {/* Presentation Check Results */}
      {data.presentation_check && data.presentation_check.issues.length > 0 && (
        <CollapsibleSection
          title={`Presentation Issues (${data.presentation_check.issues.length})`}
          icon={<Layout className="h-5 w-5 text-violet-400" />}
          defaultOpen={false}
        >
          <div className="space-y-3">
            <p className="text-sm leading-relaxed text-slate-300">
              {data.presentation_check.summary}
            </p>
            <ul className="space-y-2">
              {data.presentation_check.issues.map((issue, i) => (
                <li key={i} className="text-sm text-slate-300">
                  <span className="font-medium text-violet-400">{issue.location}</span>
                  <span className="mx-1 text-slate-500">({issue.issue_type})</span>
                  <span>{issue.description}</span>
                </li>
              ))}
            </ul>
          </div>
        </CollapsibleSection>
      )}

      {/* Ethical Concerns (NeurIPS and ICLR) */}
      {(data.conference === "neurips_2025" || data.conference === "iclr_2025") &&
        data.ethical_concerns && (
          <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-red-400 sm:p-4">
            <div className="flex items-center gap-2">
              <AlertTriangle className="h-5 w-5 shrink-0" />
              <span className="text-sm font-medium">
                Ethical concerns were identified in this paper
              </span>
            </div>
            {data.ethical_concerns_explanation && (
              <p className="mt-2 text-sm text-red-300">{data.ethical_concerns_explanation}</p>
            )}
          </div>
        )}

      {/* Ethical Issues (ICML) */}
      {data.conference === "icml" && data.ethical_issues && (
        <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-red-400 sm:p-4">
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 shrink-0" />
            <span className="text-sm font-medium">
              Ethical issues were identified in this paper
            </span>
          </div>
          {data.ethical_issues_explanation && (
            <p className="mt-2 text-sm text-red-300">{data.ethical_issues_explanation}</p>
          )}
        </div>
      )}
    </div>
  );
}
