"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { apiFetch } from "@/shared/lib/api-client";
import { cn } from "@/shared/lib/utils";
import {
  ChevronDown,
  ChevronRight,
  Target,
  Wrench,
  Sparkles,
  Zap,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  ClipboardList,
  RefreshCw,
  Shield,
  WandSparkles,
} from "lucide-react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface CriterionBase {
  score: number;
  rationale: string;
  suggestions: string[];
}

interface RelevanceCriterion extends CriterionBase {
  connection_points: string[];
  drift_concerns: string[];
}

interface FeasibilityCriterion extends CriterionBase {
  compute_viable: boolean;
  agent_implementable: boolean;
  estimated_cost: string;
  blockers: string[];
}

interface NoveltyCriterion extends CriterionBase {
  core_claims: string[];
  related_prior_work: string[];
  differentiation: string;
  novelty_risks: string[];
}

interface ImpactCriterion extends CriterionBase {
  research_question: string;
  what_changes_if_success: string;
  threat_model_assessment: string;
  goodhart_risk_assessment: string;
}

interface RevisionActionItem {
  action: string;
  addresses: string;
  priority: string;
}

interface RevisionPlan {
  action_items: RevisionActionItem[];
  overall_assessment: string;
}

interface JudgeReview {
  id: number;
  idea_id: number;
  relevance: RelevanceCriterion;
  feasibility: FeasibilityCriterion;
  novelty: NoveltyCriterion;
  impact: ImpactCriterion;
  revision: RevisionPlan | null;
  overall_score: number;
  recommendation: string;
  summary: string;
  llm_model: string | null;
  created_at: string;
}

interface JudgeReviewsResponse {
  reviews: JudgeReview[];
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const SCORE_HIGH = { bar: "bg-emerald-500", text: "text-emerald-400", bg: "bg-emerald-500/10" };
const SCORE_MID = { bar: "bg-amber-500", text: "text-amber-400", bg: "bg-amber-500/10" };
const SCORE_LOW = { bar: "bg-red-500", text: "text-red-400", bg: "bg-red-500/10" };

function scoreColor(score: number) {
  if (score >= 4) return SCORE_HIGH;
  if (score >= 3) return SCORE_MID;
  return SCORE_LOW;
}

type RecStyle = { label: string; className: string; icon: typeof CheckCircle2 };

const RECOMMENDATION_STYLES: Record<string, RecStyle> = {
  strong_accept: { label: "Strong Accept", className: "bg-emerald-500/20 text-emerald-300 border-emerald-500/30", icon: CheckCircle2 },
  accept: { label: "Accept", className: "bg-sky-500/20 text-sky-300 border-sky-500/30", icon: CheckCircle2 },
  revise: { label: "Revise", className: "bg-amber-500/20 text-amber-300 border-amber-500/30", icon: AlertTriangle },
  reject: { label: "Reject", className: "bg-red-500/20 text-red-300 border-red-500/30", icon: XCircle },
};

const DEFAULT_REC_STYLE: RecStyle = { label: "Revise", className: "bg-amber-500/20 text-amber-300 border-amber-500/30", icon: AlertTriangle };

const PRIORITY_STYLES: Record<string, string> = {
  high: "bg-red-500/15 text-red-300 border-red-500/30",
  medium: "bg-amber-500/15 text-amber-300 border-amber-500/30",
  low: "bg-slate-500/15 text-slate-300 border-slate-500/30",
};

const CRITERIA_META = [
  { key: "relevance" as const, label: "Relevance", icon: Target, description: "Connection to source conversation" },
  { key: "feasibility" as const, label: "Feasibility", icon: Wrench, description: "Executable within constraints" },
  { key: "novelty" as const, label: "Novelty", icon: Sparkles, description: "Differentiated from prior work" },
  { key: "impact" as const, label: "Impact", icon: Zap, description: "Clear and consequential research" },
];

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function ScoreBar({ score, max = 5 }: { score: number; max?: number }) {
  const pct = (score / max) * 100;
  const colors = scoreColor(score);
  return (
    <div className="flex items-center gap-2.5">
      <div className="h-2 flex-1 rounded-full bg-slate-700/60 overflow-hidden">
        <div
          className={cn("h-full rounded-full transition-all duration-700", colors.bar)}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className={cn("text-sm font-semibold tabular-nums min-w-[2.5rem] text-right", colors.text)}>
        {score}/{max}
      </span>
    </div>
  );
}

function BooleanBadge({ value, label }: { value: boolean; label: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-xs font-medium",
        value
          ? "bg-emerald-500/15 text-emerald-300 border-emerald-500/30"
          : "bg-red-500/15 text-red-300 border-red-500/30"
      )}
    >
      {value ? <CheckCircle2 className="h-3 w-3" /> : <XCircle className="h-3 w-3" />}
      {label}
    </span>
  );
}

function FindingsList({ items, className }: { items: string[]; className?: string }) {
  if (!items.length) return null;
  return (
    <ul className={cn("space-y-1.5", className)}>
      {items.map((item, i) => (
        <li key={i} className="text-sm text-slate-300 leading-relaxed flex gap-2">
          <span className="text-slate-500 mt-0.5 shrink-0">&#8226;</span>
          <span>{item}</span>
        </li>
      ))}
    </ul>
  );
}

function SuggestionsList({ items }: { items: string[] }) {
  if (!items.length) return null;
  return (
    <div className="mt-3 pt-3 border-t border-slate-700/50">
      <p className="text-xs font-medium text-slate-400 uppercase tracking-wider mb-2">Suggestions</p>
      <ul className="space-y-1.5">
        {items.map((item, i) => (
          <li key={i} className="text-sm text-sky-300/90 leading-relaxed flex gap-2">
            <span className="text-sky-500/60 mt-0.5 shrink-0">&#10132;</span>
            <span>{item}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Criterion detail panels
// ---------------------------------------------------------------------------

function RelevanceDetails({ data }: { data: RelevanceCriterion }) {
  return (
    <>
      {data.connection_points.length > 0 && (
        <div className="mb-3">
          <p className="text-xs font-medium text-slate-400 uppercase tracking-wider mb-1.5">Connection Points</p>
          <FindingsList items={data.connection_points} />
        </div>
      )}
      {data.drift_concerns.length > 0 && (
        <div className="mb-3">
          <p className="text-xs font-medium text-amber-400/80 uppercase tracking-wider mb-1.5">Drift Concerns</p>
          <FindingsList items={data.drift_concerns} />
        </div>
      )}
    </>
  );
}

function FeasibilityDetails({ data }: { data: FeasibilityCriterion }) {
  return (
    <>
      <div className="flex flex-wrap gap-2 mb-3">
        <BooleanBadge value={data.compute_viable} label="Compute Viable" />
        <BooleanBadge value={data.agent_implementable} label="Agent Implementable" />
      </div>
      {data.estimated_cost && (
        <div className="mb-3 rounded-lg bg-slate-800/50 px-3 py-2 text-sm text-slate-300">
          <span className="text-slate-400 font-medium">Est. Cost:</span> {data.estimated_cost}
        </div>
      )}
      {data.blockers.length > 0 && (
        <div className="mb-3">
          <p className="text-xs font-medium text-red-400/80 uppercase tracking-wider mb-1.5">Blockers</p>
          <FindingsList items={data.blockers} />
        </div>
      )}
    </>
  );
}

function NoveltyDetails({ data }: { data: NoveltyCriterion }) {
  return (
    <>
      {data.core_claims.length > 0 && (
        <div className="mb-3">
          <p className="text-xs font-medium text-slate-400 uppercase tracking-wider mb-1.5">Core Claims</p>
          <FindingsList items={data.core_claims} />
        </div>
      )}
      {data.differentiation && (
        <div className="mb-3 rounded-lg bg-slate-800/50 px-3 py-2 text-sm text-slate-300">
          <span className="text-slate-400 font-medium">Differentiation:</span> {data.differentiation}
        </div>
      )}
      {data.novelty_risks.length > 0 && (
        <div className="mb-3">
          <p className="text-xs font-medium text-amber-400/80 uppercase tracking-wider mb-1.5">Novelty Risks</p>
          <FindingsList items={data.novelty_risks} />
        </div>
      )}
      {data.related_prior_work.length > 0 && (
        <div className="mb-3">
          <p className="text-xs font-medium text-slate-400 uppercase tracking-wider mb-1.5">Related Prior Work</p>
          <FindingsList items={data.related_prior_work} />
        </div>
      )}
    </>
  );
}

function ImpactDetails({ data }: { data: ImpactCriterion }) {
  return (
    <>
      {data.research_question && (
        <div className="mb-3 rounded-lg bg-slate-800/50 px-3 py-2 text-sm text-slate-300">
          <span className="text-slate-400 font-medium">Research Question:</span> {data.research_question}
        </div>
      )}
      {data.what_changes_if_success && (
        <div className="mb-3">
          <p className="text-xs font-medium text-slate-400 uppercase tracking-wider mb-1.5">What Changes if Successful</p>
          <p className="text-sm text-slate-300 leading-relaxed">{data.what_changes_if_success}</p>
        </div>
      )}
      {data.threat_model_assessment && (
        <div className="mb-3">
          <p className="text-xs font-medium text-slate-400 uppercase tracking-wider mb-1.5">Threat Model Assessment</p>
          <p className="text-sm text-slate-300 leading-relaxed">{data.threat_model_assessment}</p>
        </div>
      )}
      {data.goodhart_risk_assessment && (
        <div className="mb-3">
          <p className="text-xs font-medium text-amber-400/80 uppercase tracking-wider mb-1.5">Goodhart Risk</p>
          <p className="text-sm text-slate-300 leading-relaxed">{data.goodhart_risk_assessment}</p>
        </div>
      )}
    </>
  );
}

// ---------------------------------------------------------------------------
// Criterion card
// ---------------------------------------------------------------------------

function CriterionCard({
  criterion,
  review,
}: {
  criterion: (typeof CRITERIA_META)[number];
  review: JudgeReview;
}) {
  const [expanded, setExpanded] = useState(false);
  const data = review[criterion.key] as CriterionBase;
  const Icon = criterion.icon;
  const colors = scoreColor(data.score);

  return (
    <div className="rounded-xl border border-slate-700/60 bg-slate-800/30 overflow-hidden transition-colors hover:border-slate-600/60">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full px-4 py-3 flex items-center gap-3 text-left"
      >
        <div className={cn("rounded-lg p-1.5", colors.bg)}>
          <Icon className={cn("h-4 w-4", colors.text)} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-sm font-medium text-slate-200">{criterion.label}</span>
            <span className="text-xs text-slate-500">{criterion.description}</span>
          </div>
          <ScoreBar score={data.score} />
        </div>
        {expanded ? (
          <ChevronDown className="h-4 w-4 text-slate-500 shrink-0" />
        ) : (
          <ChevronRight className="h-4 w-4 text-slate-500 shrink-0" />
        )}
      </button>

      {expanded && (
        <div className="px-4 pb-4 border-t border-slate-700/40 pt-3">
          <p className="text-sm text-slate-300 leading-relaxed mb-3">{data.rationale}</p>

          {criterion.key === "relevance" && <RelevanceDetails data={review.relevance} />}
          {criterion.key === "feasibility" && <FeasibilityDetails data={review.feasibility} />}
          {criterion.key === "novelty" && <NoveltyDetails data={review.novelty} />}
          {criterion.key === "impact" && <ImpactDetails data={review.impact} />}

          <SuggestionsList items={data.suggestions} />
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Revision plan
// ---------------------------------------------------------------------------

function RevisionPlanSection({ plan }: { plan: RevisionPlan }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="rounded-xl border border-slate-700/60 bg-slate-800/30 overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full px-4 py-3 flex items-center gap-3 text-left"
      >
        <div className="rounded-lg p-1.5 bg-violet-500/10">
          <ClipboardList className="h-4 w-4 text-violet-400" />
        </div>
        <div className="flex-1 min-w-0">
          <span className="text-sm font-medium text-slate-200">Revision Plan</span>
          <span className="text-xs text-slate-500 ml-2">
            {plan.action_items.length} action item{plan.action_items.length !== 1 ? "s" : ""}
          </span>
        </div>
        {expanded ? (
          <ChevronDown className="h-4 w-4 text-slate-500 shrink-0" />
        ) : (
          <ChevronRight className="h-4 w-4 text-slate-500 shrink-0" />
        )}
      </button>

      {expanded && (
        <div className="px-4 pb-4 border-t border-slate-700/40 pt-3">
          <p className="text-sm text-slate-300 leading-relaxed mb-4">{plan.overall_assessment}</p>
          <div className="space-y-2.5">
            {plan.action_items.map((item, i) => (
              <div
                key={i}
                className="rounded-lg border border-slate-700/40 bg-slate-800/50 px-3 py-2.5"
              >
                <div className="flex items-start gap-2">
                  <span
                    className={cn(
                      "inline-flex items-center rounded border px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider shrink-0 mt-0.5",
                      PRIORITY_STYLES[item.priority] ?? "bg-slate-500/15 text-slate-300 border-slate-500/30"
                    )}
                  >
                    {item.priority}
                  </span>
                  <div className="min-w-0">
                    <p className="text-sm text-slate-200 leading-relaxed">{item.action}</p>
                    <p className="text-xs text-slate-500 mt-1">Addresses: {item.addresses}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

interface IdeaJudgeAuditProps {
  conversationId: number;
  onIdeaRefined?: () => void;
}

const POLL_INTERVAL_MS = 8000;
const REFINE_POLL_INTERVAL_MS = 5000;

export function IdeaJudgeAudit({ conversationId, onIdeaRefined }: IdeaJudgeAuditProps) {
  const [review, setReview] = useState<JudgeReview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [collapsed, setCollapsed] = useState(false);
  const [pending, setPending] = useState(false);
  const [rerunning, setRerunning] = useState(false);
  const [refining, setRefining] = useState(false);
  const lastReviewIdRef = useRef<number | null>(null);
  const refineVersionRef = useRef<number | null>(null);

  const fetchReview = useCallback(async (isPolling = false) => {
    try {
      if (!isPolling) setLoading(true);
      setError(null);
      const data = await apiFetch<JudgeReviewsResponse>(
        `/conversations/${conversationId}/idea/judge-reviews`
      );
      if (data.reviews && data.reviews.length > 0) {
        const latest = data.reviews[0] ?? null;
        if (rerunning && latest && latest.id === lastReviewIdRef.current) {
          return;
        }
        setReview(latest);
        setPending(false);
        if (latest) {
          lastReviewIdRef.current = latest.id;
          setRerunning(false);
        }
      } else {
        setReview(null);
        setPending(true);
      }
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Failed to load judge review";
      if (msg.includes("404")) {
        setReview(null);
        setPending(false);
        setError(null);
      } else {
        setError(msg);
      }
    } finally {
      setLoading(false);
    }
  }, [conversationId, rerunning]);

  const triggerRerun = useCallback(async () => {
    try {
      setRerunning(true);
      if (review) lastReviewIdRef.current = review.id;
      await apiFetch<{ status: string }>(
        `/conversations/${conversationId}/idea/judge-reviews/run`,
        { method: "POST" }
      );
    } catch (e) {
      setRerunning(false);
      const msg = e instanceof Error ? e.message : "Failed to start judge re-run";
      setError(msg);
    }
  }, [conversationId, review]);

  const triggerRefine = useCallback(async () => {
    try {
      setRefining(true);
      const ideaRes = await apiFetch<{ idea: { active_version: { version_number: number } } }>(
        `/conversations/${conversationId}/idea`
      );
      refineVersionRef.current = ideaRes.idea.active_version.version_number;
      await apiFetch<{ status: string }>(
        `/conversations/${conversationId}/idea/refine`,
        { method: "POST" }
      );
    } catch (e) {
      setRefining(false);
      const msg = e instanceof Error ? e.message : "Failed to start refinement";
      setError(msg);
    }
  }, [conversationId]);

  useEffect(() => {
    fetchReview();
  }, [fetchReview]);

  // Poll while waiting for a new review (initial pending or re-run)
  useEffect(() => {
    const shouldPoll = (pending && !review) || rerunning;
    if (!shouldPoll) return;
    const interval = setInterval(() => fetchReview(true), POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [pending, review, rerunning, fetchReview]);

  // Poll while refining — check for a new idea version
  useEffect(() => {
    if (!refining) return;
    const poll = async () => {
      try {
        const ideaRes = await apiFetch<{ idea: { active_version: { version_number: number } } }>(
          `/conversations/${conversationId}/idea`
        );
        const currentVersion = ideaRes.idea.active_version.version_number;
        if (refineVersionRef.current !== null && currentVersion > refineVersionRef.current) {
          setRefining(false);
          onIdeaRefined?.();
        }
      } catch {
        // keep polling
      }
    };
    const interval = setInterval(poll, REFINE_POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [refining, conversationId, onIdeaRefined]);

  if (loading) {
    return (
      <div className="rounded-2xl border border-slate-700/50 bg-slate-900/50 p-6">
        <div className="flex items-center gap-3">
          <div className="h-5 w-5 animate-spin rounded-full border-2 border-slate-600 border-t-sky-400" />
          <span className="text-sm text-slate-400">Loading audit review...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-2xl border border-red-500/20 bg-red-500/5 p-4">
        <div className="flex items-center gap-2">
          <AlertTriangle className="h-4 w-4 text-red-400" />
          <span className="text-sm text-red-300">Failed to load audit: {error}</span>
          <button
            onClick={() => fetchReview()}
            className="ml-auto text-xs text-red-400 hover:text-red-300 underline"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  if (pending && !review) {
    return (
      <div className="rounded-2xl border border-slate-700/50 bg-slate-900/50 overflow-hidden">
        <div className="px-5 py-4 flex items-center gap-3">
          <div className="rounded-xl p-2 bg-slate-800 border border-slate-700/60">
            <Shield className="h-5 w-5 text-slate-500" />
          </div>
          <div className="flex-1 min-w-0">
            <h3 className="text-base font-semibold text-slate-300">Idea Audit</h3>
            <div className="flex items-center gap-2 mt-1">
              <div className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-slate-600 border-t-sky-400" />
              <p className="text-xs text-slate-500">
                Running quality review — this usually takes 30–90 seconds...
              </p>
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (!review) return null;

  const recStyle = RECOMMENDATION_STYLES[review.recommendation] ?? DEFAULT_REC_STYLE;
  const RecIcon = recStyle.icon;

  return (
    <div className="rounded-2xl border border-slate-700/50 bg-slate-900/50 overflow-hidden">
      {/* Header */}
      <div
        role="button"
        tabIndex={0}
        onClick={() => setCollapsed(!collapsed)}
        onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") setCollapsed(!collapsed); }}
        className="w-full px-5 py-4 flex items-center gap-3 text-left hover:bg-slate-800/30 transition-colors cursor-pointer select-none"
      >
        <div className="rounded-xl p-2 bg-slate-800 border border-slate-700/60">
          <Shield className="h-5 w-5 text-sky-400" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2.5 flex-wrap">
            <h3 className="text-base font-semibold text-slate-100">Idea Audit</h3>
            <span
              className={cn(
                "inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-semibold",
                recStyle.className
              )}
            >
              <RecIcon className="h-3 w-3" />
              {recStyle.label}
            </span>
            <span className={cn("text-sm font-semibold tabular-nums", scoreColor(review.overall_score).text)}>
              {review.overall_score.toFixed(1)}/5
            </span>
          </div>
          <p className="text-xs text-slate-500 mt-0.5">
            Automated quality review across relevance, feasibility, novelty, and impact
          </p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <button
            onClick={(e) => {
              e.stopPropagation();
              triggerRerun();
            }}
            disabled={rerunning}
            className={cn(
              "p-1.5 rounded-lg transition-colors",
              rerunning
                ? "text-sky-400 cursor-wait"
                : "hover:bg-slate-700/50 text-slate-500 hover:text-slate-300"
            )}
            title={rerunning ? "Re-running judge..." : "Re-run judge review"}
          >
            <RefreshCw className={cn("h-3.5 w-3.5", rerunning && "animate-spin")} />
          </button>
          {collapsed ? (
            <ChevronRight className="h-4 w-4 text-slate-500" />
          ) : (
            <ChevronDown className="h-4 w-4 text-slate-500" />
          )}
        </div>
      </div>

      {/* Body */}
      {!collapsed && (
        <div className="px-5 pb-5 space-y-2.5">
          {/* Score overview row */}
          <div className="grid grid-cols-4 gap-2 mb-1">
            {CRITERIA_META.map((c) => {
              const score = (review[c.key] as CriterionBase).score;
              const colors = scoreColor(score);
              return (
                <div key={c.key} className="text-center py-2 rounded-lg bg-slate-800/40">
                  <div className={cn("text-lg font-bold tabular-nums", colors.text)}>
                    {score}
                  </div>
                  <div className="text-[10px] text-slate-500 uppercase tracking-wider">{c.label}</div>
                </div>
              );
            })}
          </div>

          {/* Criteria cards */}
          <div className="space-y-2">
            {CRITERIA_META.map((c) => (
              <CriterionCard key={c.key} criterion={c} review={review} />
            ))}
          </div>

          {/* Revision plan */}
          {review.revision && <RevisionPlanSection plan={review.revision} />}

          {/* Refine action */}
          <button
            onClick={triggerRefine}
            disabled={refining || rerunning}
            className={cn(
              "w-full flex items-center justify-center gap-2 rounded-xl border px-4 py-2.5 text-sm font-medium transition-colors",
              refining
                ? "border-violet-500/30 bg-violet-500/10 text-violet-300 cursor-wait"
                : "border-slate-700/60 bg-slate-800/40 text-slate-200 hover:bg-violet-500/10 hover:border-violet-500/30 hover:text-violet-300"
            )}
          >
            <WandSparkles className={cn("h-4 w-4", refining && "animate-pulse")} />
            {refining ? "Refining idea..." : "Refine Idea Based on Findings"}
          </button>

          {/* Footer meta */}
          {review.llm_model && (
            <p className="text-[10px] text-slate-600 text-right pt-1">
              Reviewed by {review.llm_model} &middot;{" "}
              {new Date(review.created_at).toLocaleDateString(undefined, {
                month: "short",
                day: "numeric",
                year: "numeric",
              })}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
