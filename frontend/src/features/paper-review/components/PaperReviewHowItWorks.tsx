"use client";

import { useState } from "react";
import {
  ChevronDown,
  FileText,
  Brain,
  RefreshCw,
  BarChart3,
  Layers,
  Clock4,
  DollarSign,
} from "lucide-react";
import { cn } from "@/shared/lib/utils";

const FLOW_STEPS = [
  {
    icon: FileText,
    title: "PDF Text Extraction",
    detail:
      "Your paper’s content is parsed to capture all text while preserving its structure and formatting.",
  },
  {
    icon: Layers,
    title: "Ensemble Review Generation",
    detail:
      "Multiple independent AI reviewers analyze your paper in parallel, each providing their own assessment. This ensemble approach reduces bias and improves reliability.",
  },
  {
    icon: Brain,
    title: "Meta-Review Aggregation",
    detail:
      "When using multiple reviewers, a meta-review synthesizes all perspectives into a coherent consensus, highlighting areas of agreement and divergence.",
  },
  {
    icon: RefreshCw,
    title: "Reflection & Refinement",
    detail:
      "The AI performs multiple reflection rounds, reconsidering its initial assessment for accuracy, soundness, and clarity before finalizing the review.",
  },
  {
    icon: BarChart3,
    title: "Structured Scoring",
    detail:
      "Final review includes NeurIPS-style scores (originality, quality, clarity, significance) plus an overall rating and accept/reject decision.",
  },
];

// NeurIPS-style rating scales
const SCALE_LOW_TO_HIGH = [
  { value: "4", label: "Very high" },
  { value: "3", label: "High" },
  { value: "2", label: "Medium" },
  { value: "1", label: "Low" },
];

const SCALE_POOR_TO_EXCELLENT = [
  { value: "4", label: "Excellent" },
  { value: "3", label: "Good" },
  { value: "2", label: "Fair" },
  { value: "1", label: "Poor" },
];

const SCALE_OVERALL = [
  { value: "9-10", label: "Award level" },
  { value: "7-8", label: "Strong Accept" },
  { value: "6", label: "Solid Accept" },
  { value: "4-5", label: "Borderline" },
  { value: "1-3", label: "Reject" },
];

const SCALE_CONFIDENCE = [
  { value: "5", label: "Absolutely certain" },
  { value: "4", label: "Confident" },
  { value: "3", label: "Fairly confident" },
  { value: "2", label: "Uncertain" },
  { value: "1", label: "Educated guess" },
];

// All review criteria with their scales (matching NeurIPS form)
const REVIEW_CRITERIA = [
  { name: "Originality", desc: "Novelty of ideas and approach", scores: SCALE_LOW_TO_HIGH },
  { name: "Quality", desc: "Technical correctness and rigor", scores: SCALE_LOW_TO_HIGH },
  { name: "Clarity", desc: "Writing and exposition quality", scores: SCALE_LOW_TO_HIGH },
  { name: "Significance", desc: "Potential impact on the field", scores: SCALE_LOW_TO_HIGH },
  { name: "Soundness", desc: "Methodological rigor", scores: SCALE_POOR_TO_EXCELLENT },
  { name: "Presentation", desc: "Presentation quality", scores: SCALE_POOR_TO_EXCELLENT },
  { name: "Contribution", desc: "Contribution level", scores: SCALE_POOR_TO_EXCELLENT },
  { name: "Overall", desc: "Overall assessment", scores: SCALE_OVERALL },
  { name: "Confidence", desc: "Reviewer confidence", scores: SCALE_CONFIDENCE },
];

interface PaperReviewHowItWorksProps {
  className?: string;
}

export function PaperReviewHowItWorks({ className }: PaperReviewHowItWorksProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  return (
    <div
      className={cn("rounded-xl border border-slate-800 bg-slate-900/50 sm:rounded-2xl", className)}
    >
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="flex w-full items-center justify-between p-3 text-left transition-colors hover:bg-slate-800/30 sm:p-4"
      >
        <div className="flex items-center gap-2 sm:gap-3">
          <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-sky-500/20 sm:h-8 sm:w-8">
            <Brain className="h-3.5 w-3.5 text-sky-400 sm:h-4 sm:w-4" />
          </div>
          <div>
            <h3 className="text-sm font-medium text-white sm:text-base">How Paper Review Works</h3>
            <p className="text-xs text-slate-400 sm:text-sm">
              Learn about our AI-powered peer review process
            </p>
          </div>
        </div>
        <ChevronDown
          className={cn(
            "h-5 w-5 shrink-0 text-slate-400 transition-transform",
            isExpanded && "rotate-180"
          )}
        />
      </button>

      {isExpanded && (
        <div className="border-t border-slate-800 p-3 sm:p-4">
          {/* Process Flow */}
          <div className="space-y-2 sm:space-y-3">
            {FLOW_STEPS.map((step, index) => {
              const Icon = step.icon;
              return (
                <div
                  key={step.title}
                  className="flex gap-2 rounded-lg border border-slate-800/60 bg-slate-900/40 p-2.5 sm:gap-3 sm:p-3"
                >
                  <div className="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full bg-sky-500/20 sm:h-8 sm:w-8">
                    <span className="text-xs font-semibold text-sky-300">{index + 1}</span>
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-1.5 sm:gap-2">
                      <Icon className="h-3.5 w-3.5 text-sky-400 sm:h-4 sm:w-4" />
                      <span className="text-sm font-medium text-white sm:text-base">
                        {step.title}
                      </span>
                    </div>
                    <p className="mt-1 text-xs text-slate-400 sm:text-sm">{step.detail}</p>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Review Criteria - 3x3 Grid */}
          <div className="mt-3 sm:mt-4">
            <h4 className="mb-2 text-sm font-semibold text-white sm:mb-3">
              Review Criteria (NeurIPS-style)
            </h4>

            <div className="grid grid-cols-2 gap-2 sm:grid-cols-2 sm:gap-3 lg:grid-cols-3">
              {REVIEW_CRITERIA.map(criterion => (
                <div
                  key={criterion.name}
                  className="rounded-lg border border-slate-800/60 bg-slate-900/40 p-2 sm:p-3"
                >
                  <h5 className="text-xs font-semibold text-sky-400 sm:text-sm">
                    {criterion.name}
                  </h5>
                  <p className="mb-1.5 text-[10px] text-slate-500 sm:mb-2 sm:text-xs">
                    {criterion.desc}
                  </p>
                  <div className="space-y-0.5">
                    {criterion.scores.map(score => (
                      <div
                        key={score.value}
                        className="flex items-center gap-1.5 text-[10px] sm:gap-2 sm:text-xs"
                      >
                        <span className="w-6 font-medium text-slate-400 sm:w-8">{score.value}</span>
                        <span className="text-slate-500">{score.label}</span>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Cost & Duration Info */}
          <div className="mt-3 grid gap-2 sm:mt-4 sm:grid-cols-2 sm:gap-3">
            <div className="rounded-lg border border-slate-800/60 bg-slate-900/40 p-2.5 sm:p-3">
              <div className="flex items-center gap-2 text-[10px] uppercase tracking-widest text-slate-400 sm:text-xs">
                <Clock4 className="h-3 w-3 text-sky-300 sm:h-3.5 sm:w-3.5" />
                Duration
              </div>
              <p className="mt-1 text-base font-semibold text-white sm:text-lg">2-5 minutes</p>
              <p className="text-[10px] text-slate-500 sm:text-xs">
                Varies based on paper length and model.
              </p>
            </div>
            <div className="rounded-lg border border-slate-800/60 bg-slate-900/40 p-2.5 sm:p-3">
              <div className="flex items-center gap-2 text-[10px] uppercase tracking-widest text-slate-400 sm:text-xs">
                <DollarSign className="h-3 w-3 text-emerald-300 sm:h-3.5 sm:w-3.5" />
                Cost
              </div>
              <p className="mt-1 text-base font-semibold text-white sm:text-lg">&lt; $1</p>
              <p className="text-[10px] text-slate-500 sm:text-xs">
                Typically $0.30-$0.50 per review.
              </p>
            </div>
          </div>

          {/* Configuration Note */}
          <p className="mt-3 text-xs text-slate-400 sm:mt-4 sm:text-sm">
            Reviews use 3 ensemble reviewers with 2 reflection rounds by default.
          </p>
          <p className="mt-1.5 text-xs text-slate-400 sm:mt-2 sm:text-sm">
            If your balance goes negative during the execution, review results are locked until you
            add credits.
          </p>
        </div>
      )}
    </div>
  );
}
