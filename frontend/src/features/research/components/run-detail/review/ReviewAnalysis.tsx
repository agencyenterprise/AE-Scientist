"use client";

import { useState } from "react";
import { ChevronDown } from "lucide-react";
import { cn } from "@/shared/lib/utils";
import type { LlmReviewResponse } from "@/types/research";

interface ReviewAnalysisProps {
  review: LlmReviewResponse;
}

interface Section {
  id: string;
  title: string;
  content: React.ReactNode;
  defaultExpanded: boolean;
  shouldShow: boolean;
  color: "emerald" | "amber" | "sky" | "slate";
}

/**
 * ReviewAnalysis Component
 *
 * Displays qualitative evaluation data in collapsible sections.
 * Features:
 * - Summary: Text paragraph, expanded by default
 * - Strengths: Green bullet list, expanded by default
 * - Weaknesses: Amber bullet list, collapsed by default
 * - Questions: Sky bullet list, collapsed, hidden if empty
 * - Limitations: Gray bullet list, collapsed, hidden if empty
 * - Ethical concerns banner (conditional)
 *
 * Collapsible sections allow users to focus on specific areas of interest.
 *
 * @param review - The LlmReviewResponse object containing qualitative data
 */
export function ReviewAnalysis({ review }: ReviewAnalysisProps) {
  const [expandedSections, setExpandedSections] = useState<Record<string, boolean>>({
    summary: true,
    strengths: true,
    weaknesses: false,
    questions: false,
    limitations: false,
  });

  const toggleSection = (sectionId: string) => {
    setExpandedSections(prev => ({
      ...prev,
      [sectionId]: !prev[sectionId],
    }));
  };

  const bulletColor = (color: string) => {
    const colors: Record<string, string> = {
      emerald: "text-emerald-400 marker:text-emerald-400",
      amber: "text-amber-400 marker:text-amber-400",
      sky: "text-sky-400 marker:text-sky-400",
      slate: "text-slate-400 marker:text-slate-400",
    };
    return colors[color] || "";
  };

  const sections: Section[] = [
    {
      id: "summary",
      title: "Summary",
      content: <p className="text-foreground whitespace-pre-wrap">{review.summary}</p>,
      defaultExpanded: true,
      shouldShow: true,
      color: "sky",
    },
    {
      id: "strengths",
      title: "Strengths",
      content: (
        <ul className={cn("list-disc list-inside space-y-2", bulletColor("emerald"))}>
          {review.strengths.map((strength, idx) => (
            <li key={idx} className="text-foreground">
              {strength}
            </li>
          ))}
        </ul>
      ),
      defaultExpanded: true,
      shouldShow: review.strengths.length > 0,
      color: "emerald",
    },
    {
      id: "weaknesses",
      title: "Weaknesses",
      content: (
        <ul className={cn("list-disc list-inside space-y-2", bulletColor("amber"))}>
          {review.weaknesses.map((weakness, idx) => (
            <li key={idx} className="text-foreground">
              {weakness}
            </li>
          ))}
        </ul>
      ),
      defaultExpanded: false,
      shouldShow: review.weaknesses.length > 0,
      color: "amber",
    },
    {
      id: "questions",
      title: "Questions",
      content: (
        <ul className={cn("list-disc list-inside space-y-2", bulletColor("sky"))}>
          {review.questions.map((question, idx) => (
            <li key={idx} className="text-foreground">
              {question}
            </li>
          ))}
        </ul>
      ),
      defaultExpanded: false,
      shouldShow: review.questions.length > 0,
      color: "sky",
    },
    {
      id: "limitations",
      title: "Limitations",
      content: (
        <ul className={cn("list-disc list-inside space-y-2", bulletColor("slate"))}>
          {review.limitations.map((limitation, idx) => (
            <li key={idx} className="text-foreground">
              {limitation}
            </li>
          ))}
        </ul>
      ),
      defaultExpanded: false,
      shouldShow: review.limitations.length > 0,
      color: "slate",
    },
  ];

  const visibleSections = sections.filter(s => s.shouldShow);

  return (
    <div>
      <h3 className="text-lg font-semibold mb-4">📋 Qualitative Analysis</h3>

      {/* Ethical concerns banner */}
      {review.ethical_concerns && (
        <div className="bg-red-500/15 border border-red-500/30 text-red-400 p-3 rounded mb-4">
          ⚠️ Ethical concerns were identified in this research
        </div>
      )}

      {/* Collapsible sections */}
      <div className="space-y-0 border border-border rounded-lg overflow-hidden">
        {visibleSections.map((section, idx) => (
          <div
            key={section.id}
            className={cn(idx !== visibleSections.length - 1 && "border-b border-border")}
          >
            <button
              onClick={() => toggleSection(section.id)}
              className="flex items-center justify-between w-full py-3 px-4 text-left hover:bg-muted/50 transition"
            >
              <span className="font-medium text-foreground">{section.title}</span>
              <ChevronDown
                className={cn(
                  "h-4 w-4 text-muted-foreground transition-transform",
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
  );
}
