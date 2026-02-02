"use client";

import { useState } from "react";
import { ChevronDown, FileText, Brain, RefreshCw, BarChart3, Layers } from "lucide-react";
import { cn } from "@/shared/lib/utils";

const FLOW_STEPS = [
  {
    icon: FileText,
    title: "PDF Text Extraction",
    detail:
      "Your paper is securely uploaded and parsed using advanced PDF extraction to capture all text content, preserving structure and formatting.",
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
// For Originality, Quality, Clarity, Significance
const SCALE_LOW_TO_HIGH = [
  { value: 4, label: "Very high" },
  { value: 3, label: "High" },
  { value: 2, label: "Medium" },
  { value: 1, label: "Low" },
];

// For Soundness, Presentation, Contribution
const SCALE_POOR_TO_EXCELLENT = [
  { value: 4, label: "Excellent" },
  { value: 3, label: "Good" },
  { value: 2, label: "Fair" },
  { value: 1, label: "Poor" },
];

const REVIEW_CRITERIA = [
  {
    label: "Originality",
    description: "Novelty of ideas and approach",
    scale: SCALE_LOW_TO_HIGH,
  },
  {
    label: "Quality",
    description: "Technical correctness and rigor",
    scale: SCALE_LOW_TO_HIGH,
  },
  {
    label: "Clarity",
    description: "Writing and exposition quality",
    scale: SCALE_LOW_TO_HIGH,
  },
  {
    label: "Significance",
    description: "Potential impact on the field",
    scale: SCALE_LOW_TO_HIGH,
  },
  {
    label: "Soundness",
    description: "Methodological rigor",
    scale: SCALE_POOR_TO_EXCELLENT,
  },
  {
    label: "Presentation",
    description: "Presentation quality",
    scale: SCALE_POOR_TO_EXCELLENT,
  },
  {
    label: "Contribution",
    description: "Contribution level",
    scale: SCALE_POOR_TO_EXCELLENT,
  },
  {
    label: "Overall",
    description: "Overall assessment",
    scale: [
      { value: "9-10", label: "Award level" },
      { value: "7-8", label: "Strong Accept" },
      { value: "6", label: "Solid Accept" },
      { value: "4-5", label: "Borderline" },
      { value: "1-3", label: "Reject" },
    ],
  },
  {
    label: "Confidence",
    description: "Reviewer confidence",
    scale: [
      { value: 5, label: "Absolutely certain" },
      { value: 4, label: "Confident" },
      { value: 3, label: "Fairly confident" },
      { value: 2, label: "Uncertain" },
      { value: 1, label: "Educated guess" },
    ],
  },
];

interface PaperReviewHowItWorksProps {
  className?: string;
}

export function PaperReviewHowItWorks({ className }: PaperReviewHowItWorksProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  return (
    <div className={cn("rounded-xl border border-slate-800 bg-slate-900/50", className)}>
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="flex w-full items-center justify-between p-4 text-left transition-colors hover:bg-slate-800/30"
      >
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-sky-500/20">
            <Brain className="h-4 w-4 text-sky-400" />
          </div>
          <div>
            <h3 className="font-medium text-white">How Paper Review Works</h3>
            <p className="text-sm text-slate-400">Learn about our AI-powered peer review process</p>
          </div>
        </div>
        <ChevronDown
          className={cn("h-5 w-5 text-slate-400 transition-transform", isExpanded && "rotate-180")}
        />
      </button>

      {isExpanded && (
        <div className="border-t border-slate-800 p-4 pt-4">
          {/* Process Flow */}
          <div className="space-y-3">
            {FLOW_STEPS.map((step, index) => {
              const Icon = step.icon;
              return (
                <div
                  key={step.title}
                  className="flex gap-3 rounded-lg border border-slate-800/60 bg-slate-900/40 p-3"
                >
                  <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-sky-500/20">
                    <span className="text-xs font-semibold text-sky-300">{index + 1}</span>
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <Icon className="h-4 w-4 text-sky-400" />
                      <span className="font-medium text-white">{step.title}</span>
                    </div>
                    <p className="mt-1 text-sm text-slate-400">{step.detail}</p>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Review Criteria */}
          <div className="mt-4 rounded-lg border border-slate-800/60 bg-slate-900/40 p-4">
            <h4 className="mb-3 text-sm font-semibold text-white">
              Review Criteria (NeurIPS-style)
            </h4>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {REVIEW_CRITERIA.map(criteria => (
                <div
                  key={criteria.label}
                  className="rounded-md border border-slate-700/50 bg-slate-800/30 p-3"
                >
                  <div className="text-sm font-medium text-sky-300">{criteria.label}</div>
                  <div className="mt-0.5 text-xs text-slate-500">{criteria.description}</div>
                  <div className="mt-2 space-y-0.5">
                    {criteria.scale.map(item => (
                      <div key={item.value} className="flex items-center gap-2 text-xs">
                        <span className="w-8 text-right font-mono text-slate-400">
                          {item.value}
                        </span>
                        <span className="text-slate-500">{item.label}</span>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Configuration Note */}
          <p className="mt-4 text-xs text-slate-500">
            Reviews use 3 ensemble reviewers with 2 reflection rounds by default. The process
            typically completes in 1-3 minutes depending on paper length.
          </p>
        </div>
      )}
    </div>
  );
}
