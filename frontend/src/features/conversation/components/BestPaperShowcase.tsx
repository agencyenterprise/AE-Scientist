"use client";

import * as Sentry from "@sentry/nextjs";
import { useState } from "react";
import { ChevronDown, Download, FileText, Lightbulb, Trophy } from "lucide-react";
import { cn } from "@/shared/lib/utils";
import { api } from "@/shared/lib/api-client-typed";
import { Markdown } from "@/shared/components/Markdown";

// Research title from the input
const RESEARCH_TITLE =
  "Rare/Synthetic Token Persistence Under Continued Fine-Tuning: A Reproducible, Causal Study of Where Forgetting Lives (Head vs Features)";

// Full research idea markdown
const RESEARCH_IDEA = `## Short Hypothesis

**Core falsifiable hypothesis (now explicitly causal):** After Stage-1 installation, Stage-2 forgetting is primarily caused by _misalignment between the token's readout row(s) and the residual-stream features that previously supported that token_, and this misalignment can be decomposed into two separable causal mechanisms:

- **H1 (Head/Readout drift dominates):** changes in **unembedding + final LN** are sufficient to induce most forgetting even when the transformer body is frozen; restoring (or swapping back) the head largely restores retention.
- **H2 (Feature drift dominates):** changes in the **upper transformer blocks** (residual features) are sufficient to induce most forgetting even when the head is frozen; restoring (or swapping back) the upper blocks largely restores retention.

We will adjudicate H1 vs H2 via **swap/restore experiments** and **counterfactual logit restoration** that produce _causal_, not correlational, evidence.

**Make-or-break predictions:**

1. **Head/body swap test:** Let θ₁ be Stage-1 weights, θ₂ be Stage-2 weights. Construct hybrid models by mixing (a) head+LN and (b) body blocks. If forgetting is head-dominated then:
   - Model = body(θ₂) + head(θ₁) recovers retention substantially.
   - Model = body(θ₁) + head(θ₂) loses retention substantially.
     (Opposite pattern if feature-dominated.)
2. **Targeted restoration ("surgical rollback"):** Rolling back only unembedding rows for installed tokens, or only final LN, or only last k blocks produces predictable retention recovery patterns aligned with H1/H2.
3. **First-order logit decomposition predicts intervention outcomes:** For installed token t under prompt p, the larger term predicts which restoration (head vs body) recovers logits.
4. **Embedding drift remains neither necessary nor sufficient** once head/body causes are isolated; freezing embeddings alone will not match the best head/body restoration conditions.

## Related Work

- Continual learning & catastrophic forgetting (EWC, L2-SP, replay, parameter isolation, gradient interference).
- Representation drift & readout alignment (logit lens, linear probes, CKA/RSA, last-layer specialization).
- Vocab extension vs rare token behavior; tied vs untied embeddings; parameter-efficient finetuning placement.
- Model editing / causal parameter interventions (surgical weight rollback, module swapping).

## Abstract

We propose a reproducible two-stage benchmark to study whether newly installed rare/synthetic tokens persist after continued fine-tuning on unrelated data that excludes them. Beyond documenting forgetting, we aim to localize _where it lives causally_ by separating **head/readout drift** from **upper-layer feature drift**. We install synthetic tokens (and additional variants: rare existing tokens and multi-token strings) to high mastery with strict held-out templates and controls. In Stage-2 we fine-tune on unrelated corpora while selecting hyperparameters/checkpoints solely by Stage-2 validation loss, measuring retention only post-selection to mirror real deployment pipelines. Mechanistically, we combine drift diagnostics with **module swap and targeted restoration** experiments that causally test whether forgetting is driven primarily by the unembedding/final-LN pathway or by feature drift in the last transformer blocks.

## Experiments

### 0) Address the top reject reason: move from correlational to causal mechanism

**0.1 Module swap / hybridization (primary causal test)**
Train Stage-1 → Stage-2 as before to obtain θ₁ and θ₂. Evaluate retention and Stage-2 loss for hybrids:

- **Hybrid A (head rollback):** body(θ₂) + {final LN + unembedding}(θ₁)
- **Hybrid B (body rollback):** body(θ₁) + {final LN + unembedding}(θ₂)
- **Hybrid C (upper-k rollback sweep):** body blocks 1..N−k from θ₂, last k blocks from θ₁

### 1) Statistical robustness

**Core requirement:** ≥10 seeds _paired across conditions_ for the key claims including baseline, freeze embeddings, freeze head+final LN, freeze last k blocks, weight tying vs untied, and replay fraction curves.

### 2) Fix instrumentation and reporting reliability

- A single pipeline that regenerates every table/plot from raw logs
- Unit checks for consistent normalization/scales
- Gradient-alignment debug & replacement metrics

### 3) External validity

- **Token/task variants:** New vocab token extension, existing rare tokens, multi-token strings
- **Evaluation variants:** Next-token accuracy, generation, context robustness
- **Model scale:** distilgpt2 (core) + one larger open model

## Expected Outcome

- A causal adjudication of whether forgetting is primarily head/readout drift or upper-layer feature drift
- Robust multi-seed estimates of retention-adaptation tradeoffs (Pareto frontiers)
- Evidence for generality across vocab extension vs existing rare tokens vs multi-token strings
- A truly auditable benchmark with reproducible plots and verified instrumentation

## Risk Factors and Limitations

- **Hybrid swap may shift Stage-2 loss:** Mitigation: report both retention and Stage-2 loss for hybrids
- **Nonlinear interactions across modules:** Mitigation: perform k-sweeps and fine-grained restoration
- **Compute cost of multi-seed + scale:** Mitigation: prioritize decisive causal tests on distilgpt2
- **Rare token selection bias:** Mitigation: use multiple rare-token sets; include synthetic multi-token strings as control`;

// Scores from the best paper analysis
// For 1-4 scales: 4=Excellent, 3=Good, 2=Fair, 1=Poor
// For Overall (1-10): 9-10=Award level, 7-8=Strong Accept, 6=Solid Accept, 4-5=Borderline, 1-3=Reject
// For Confidence (1-5): 5=Absolutely certain, 4=Confident, 3=Fairly confident, 2=Uncertain, 1=Educated guess
const SCORES = [
  { label: "Originality", value: 3, max: 4, displayLabel: "Good" },
  { label: "Quality", value: 3, max: 4, displayLabel: "Good" },
  { label: "Clarity", value: 3, max: 4, displayLabel: "Good" },
  { label: "Significance", value: 3, max: 4, displayLabel: "Good" },
  { label: "Soundness", value: 3, max: 4, displayLabel: "Good" },
  { label: "Presentation", value: 3, max: 4, displayLabel: "Good" },
  { label: "Contribution", value: 3, max: 4, displayLabel: "Good" },
  { label: "Overall", value: 6, displayLabel: "Solid Accept" },
  { label: "Confidence", value: 3, displayLabel: "Fairly confident" },
];

const SUMMARY = `The paper studies a controlled "token forgetting" phenomenon in sequential fine-tuning when checkpoint selection is driven only by the current objective. Using distilgpt2, Stage 1 "installs" 8 synthetic strings that each map to a single new token id, reaching perfect held-out next-token accuracy on carrier prompts. Stage 2 fine-tunes on WikiText-2 while excluding these installed tokens and selects the checkpoint solely by minimum Stage-2 validation loss; retention is evaluated only after this selection and drops substantially (reported 1.0 → 0.479 micro accuracy in the main run). The core scientific question is where forgetting lives causally: in the readout pathway ("head": final layer norm LN_f and unembedding W_U) versus in upper-layer residual-stream features ("body") and their alignment with the head.`;

const STRENGTHS = [
  "Clear, deployment-motivated setup: Stage-2 checkpoint selection ignores retention, matching realistic pipelines where earlier capabilities are out-of-objective and thus can silently degrade.",
  'Causal localization is the main novelty: module swaps and targeted rollbacks manipulate disjoint parameter groups to adjudicate "head drift" vs "feature drift" more directly than representation-similarity diagnostics alone.',
  "Converging evidence in the main run: head rollback provides only modest retention recovery (~0.50) whereas body rollback restores perfect retention (1.0) but destroys Stage-2 loss.",
  "The paper connects diagnostics to interventions: the logit-drift decomposition reports the feature term dominating the head term by >10×.",
  "Includes several ablations probing training/selection knobs (weight decay sweep; optimizer moment carryover; freezing strategies; checkpoint selection criteria).",
];

const WEAKNESSES = [
  "Robustness is limited: the paper appears to rely heavily on single-seed point estimates for key causal claims.",
  "External validity remains uncertain: the core evidence is for synthetic single-token strings with carrier prompts on a small model (distilgpt2).",
  'The "head" grouping conflates LN_f and W_U; the causal attribution within the head is less sharp.',
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
    researchIdea: false,
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
      Sentry.captureException(error);
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

  const reviewSections: Section[] = [
    {
      id: "summary",
      title: "Review Summary",
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
    <div className={cn("space-y-6", className)}>
      {/* Main Header */}
      <div>
        <div className="flex items-center gap-2 text-xs uppercase tracking-[0.2em] text-slate-400">
          <Trophy className="h-4 w-4 text-amber-400" />
          <span>Example Output</span>
        </div>
        <h3 className="mt-2 text-lg font-semibold text-white">Best Paper Produced</h3>
        <p className="mt-1 text-slate-300 text-sm">
          See what AE Scientist can produce. This paper received an &quot;Accept&quot; decision from
          our automated peer review system with an overall score of 6/10.
        </p>
      </div>

      {/* ===== INPUT SECTION ===== */}
      <div className="rounded-xl border border-violet-800/40 bg-violet-950/20 p-5">
        <div className="flex items-center gap-2 text-xs uppercase tracking-[0.2em] text-violet-400 mb-4">
          <Lightbulb className="h-4 w-4" />
          <span>User Input</span>
        </div>

        {/* Research Title */}
        <div className="mb-4">
          <div className="text-xs text-violet-400/80 uppercase tracking-wide mb-1">
            Research Title
          </div>
          <p className="text-sm font-medium text-violet-100">{RESEARCH_TITLE}</p>
        </div>

        {/* Full Research Idea (collapsible) */}
        <div className="border border-violet-800/40 rounded-lg overflow-hidden">
          <button
            onClick={() => toggleSection("researchIdea")}
            className="flex items-center justify-between w-full py-3 px-4 text-left hover:bg-violet-800/20 transition"
          >
            <span className="font-medium text-violet-200">Full Research Idea</span>
            <ChevronDown
              className={cn(
                "h-4 w-4 text-violet-400 transition-transform",
                expandedSections.researchIdea && "rotate-180"
              )}
            />
          </button>
          {expandedSections.researchIdea && (
            <div className="px-4 pb-4 text-sm text-violet-100/90">
              <Markdown className="prose-invert prose-violet prose-sm max-w-none">
                {RESEARCH_IDEA}
              </Markdown>
            </div>
          )}
        </div>
      </div>

      {/* ===== OUTPUT SECTION ===== */}
      <div className="rounded-xl border border-emerald-800/40 bg-emerald-950/20 p-5">
        <div className="flex items-center gap-2 text-xs uppercase tracking-[0.2em] text-emerald-400 mb-4">
          <FileText className="h-4 w-4" />
          <span>Generated Output</span>
        </div>

        {/* Download Banner - at the top */}
        <div className="rounded-lg border border-emerald-700/50 bg-emerald-950/40 p-4 mb-5">
          <div className="flex items-center justify-between">
            <div className="flex items-start gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-emerald-500/20">
                <FileText className="h-5 w-5 text-emerald-400" />
              </div>
              <div>
                <h4 className="text-sm font-semibold text-emerald-100">Download Full Paper</h4>
                <p className="text-xs text-emerald-300/80 mt-0.5">
                  View the complete research paper with all figures and analysis
                </p>
              </div>
            </div>
            <button
              onClick={handleDownload}
              disabled={isDownloading}
              className="flex items-center justify-center gap-2 rounded border border-emerald-600 bg-emerald-500/20 px-4 py-2 text-sm font-medium text-emerald-100 transition-colors hover:bg-emerald-500/30 disabled:opacity-50 disabled:cursor-not-allowed"
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
          {downloadError && <div className="mt-2 text-xs text-red-400">{downloadError}</div>}
        </div>

        {/* Paper Analysis Section */}
        <div>
          <h4 className="text-sm font-semibold text-emerald-100 mb-3">Paper Analysis</h4>

          {/* Scores Grid */}
          <div className="grid grid-cols-3 gap-2 mb-4">
            {SCORES.map(metric => (
              <div
                key={metric.label}
                className="rounded-lg border border-emerald-800/40 bg-emerald-950/30 p-3"
              >
                <div className="text-xs text-emerald-400/80 uppercase tracking-wide mb-1">
                  {metric.label}
                </div>
                <div className="text-lg font-bold text-amber-300">
                  {metric.value}
                  {"max" in metric && (
                    <span className="text-sm text-slate-500 font-normal">/{metric.max}</span>
                  )}
                </div>
                {"displayLabel" in metric && (
                  <div className="text-xs text-slate-400 mt-0.5">{metric.displayLabel}</div>
                )}
              </div>
            ))}
          </div>

          {/* Review Sections */}
          <div className="space-y-0 border border-emerald-800/40 rounded-lg overflow-hidden">
            {reviewSections.map((section, idx) => (
              <div
                key={section.id}
                className={cn(
                  idx !== reviewSections.length - 1 && "border-b border-emerald-800/40"
                )}
              >
                <button
                  onClick={() => toggleSection(section.id)}
                  className="flex items-center justify-between w-full py-3 px-4 text-left hover:bg-emerald-800/20 transition"
                >
                  <span className="font-medium text-emerald-100">{section.title}</span>
                  <ChevronDown
                    className={cn(
                      "h-4 w-4 text-emerald-400 transition-transform",
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
        </div>
      </div>
    </div>
  );
}
