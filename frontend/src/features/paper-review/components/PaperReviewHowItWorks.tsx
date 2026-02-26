"use client";

import { useState } from "react";
import {
  ChevronDown,
  FileText,
  Brain,
  RefreshCw,
  BarChart3,
  Globe,
  Clock4,
  DollarSign,
} from "lucide-react";
import { cn } from "@/shared/lib/utils";

const FLOW_STEPS = [
  {
    icon: FileText,
    title: "PDF Processing",
    detail:
      "Your paper's content is parsed to capture all text while preserving its structure and formatting.",
  },
  {
    icon: Brain,
    title: "Analysis & Scoring",
    detail:
      "The AI reviewer analyzes your paper against the selected conference review form, producing structured scores and detailed feedback.",
  },
  {
    icon: Globe,
    title: "Web-Grounded Checks",
    detail:
      "Novelty is assessed by searching for related work, and citations are verified against Semantic Scholar. Premium tier also checks for missing references and presentation quality.",
  },
  {
    icon: RefreshCw,
    title: "Reflection & Refinement",
    detail:
      "The AI reconsiders its initial assessment for accuracy, soundness, and clarity before finalizing the review.",
  },
  {
    icon: BarChart3,
    title: "Structured Output",
    detail:
      "Final review includes conference-specific scores, strengths, weaknesses, questions, and an accept/reject decision.",
  },
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

          {/* Cost & Duration Info */}
          <div className="mt-3 grid gap-2 sm:mt-4 sm:grid-cols-2 sm:gap-3">
            <div className="rounded-lg border border-slate-800/60 bg-slate-900/40 p-2.5 sm:p-3">
              <div className="flex items-center gap-2 text-[10px] uppercase tracking-widest text-slate-400 sm:text-xs">
                <Clock4 className="h-3 w-3 text-sky-300 sm:h-3.5 sm:w-3.5" />
                Duration
              </div>
              <div className="mt-1 flex items-baseline gap-3">
                <div>
                  <span className="text-base font-semibold text-white sm:text-lg">~2 min</span>
                  <span className="ml-1 text-xs text-slate-500">Standard</span>
                </div>
                <div>
                  <span className="text-base font-semibold text-white sm:text-lg">~5 min</span>
                  <span className="ml-1 text-xs text-slate-500">Premium</span>
                </div>
              </div>
            </div>
            <div className="rounded-lg border border-slate-800/60 bg-slate-900/40 p-2.5 sm:p-3">
              <div className="flex items-center gap-2 text-[10px] uppercase tracking-widest text-slate-400 sm:text-xs">
                <DollarSign className="h-3 w-3 text-emerald-300 sm:h-3.5 sm:w-3.5" />
                Cost
              </div>
              <div className="mt-1 flex items-baseline gap-3">
                <div>
                  <span className="text-base font-semibold text-white sm:text-lg">~$0.23</span>
                  <span className="ml-1 text-xs text-slate-500">Standard</span>
                </div>
                <div>
                  <span className="text-base font-semibold text-white sm:text-lg">~$3.45</span>
                  <span className="ml-1 text-xs text-slate-500">Premium</span>
                </div>
              </div>
            </div>
          </div>

          <p className="mt-3 text-xs text-slate-400 sm:mt-4 sm:text-sm">
            If your balance goes negative during execution, review results are locked until you add
            credits.
          </p>
        </div>
      )}
    </div>
  );
}
