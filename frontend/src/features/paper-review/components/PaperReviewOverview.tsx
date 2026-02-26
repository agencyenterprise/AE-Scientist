"use client";

import {
  BarChart3,
  Search,
  BookCheck,
  BookOpen,
  FileCheck,
  GraduationCap,
  TrendingUp,
  Target,
  Award,
} from "lucide-react";

const PROOF_POINTS = [
  {
    icon: TrendingUp,
    stat: "2.65 vs 2.36",
    label: "More actionable than human peer review",
    detail: "On a 1\u20133 actionability scale, independently scored by domain experts",
    color: "text-emerald-400",
    bgColor: "bg-emerald-500/10",
  },
  {
    icon: Target,
    stat: "2x coverage",
    label: "Identifies twice as many issues",
    detail:
      "19+ weaknesses per review vs 9 for human reviewers, catching ~70% of the exact issues humans identify",
    color: "text-sky-400",
    bgColor: "bg-sky-500/10",
  },
  {
    icon: Award,
    stat: "85% accuracy",
    label: "Accept/reject agreement",
    detail:
      "Validated against actual NeurIPS and ICLR decisions on 50 papers. Substantial agreement (\u03BA = 0.71) with human review panels",
    color: "text-amber-400",
    bgColor: "bg-amber-500/10",
  },
];

const FEATURES = [
  {
    icon: BarChart3,
    label: "Structured feedback across 10 weakness categories with severity ratings",
  },
  {
    icon: Search,
    label: "Web-grounded novelty assessment: checks claims against published literature",
  },
  {
    icon: BookCheck,
    label: "Citation verification: validates referenced works exist and support claims",
  },
  { icon: BookOpen, label: "Missing reference detection: identifies works the paper should cite" },
  { icon: FileCheck, label: "Presentation quality analysis: figures, tables, formatting" },
  { icon: GraduationCap, label: "Conference-specific scoring calibrated to NeurIPS, ICLR" },
];

export function PaperReviewOverview() {
  return (
    <div className="space-y-6">
      {/* Hero */}
      <div>
        <h1 className="text-xl font-semibold text-white sm:text-2xl">AI Paper Review</h1>
        <p className="mt-2 text-sm text-slate-400 sm:text-base">
          Get thorough, conference-quality reviews of your research papers. Our AI reviewer provides
          structured feedback, identifies weaknesses, verifies citations, and scores your paper
          using official conference review forms.
        </p>
      </div>

      {/* Proof points */}
      <div className="grid gap-3 sm:grid-cols-3">
        {PROOF_POINTS.map(point => {
          const Icon = point.icon;
          return (
            <div
              key={point.label}
              className="rounded-xl border border-slate-800/60 bg-slate-900/40 p-4"
            >
              <div className={`inline-flex rounded-lg p-2 ${point.bgColor}`}>
                <Icon className={`h-4 w-4 ${point.color}`} />
              </div>
              <p className={`mt-2 text-lg font-bold ${point.color}`}>{point.stat}</p>
              <p className="text-sm font-medium text-white">{point.label}</p>
              <p className="mt-0.5 text-xs text-slate-500">{point.detail}</p>
            </div>
          );
        })}
      </div>

      {/* Feature list */}
      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
        {FEATURES.map(feature => {
          const Icon = feature.icon;
          return (
            <div key={feature.label} className="flex items-center gap-2.5 px-1 py-1.5">
              <Icon className="h-4 w-4 shrink-0 text-sky-400" />
              <span className="text-sm text-slate-300">{feature.label}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
