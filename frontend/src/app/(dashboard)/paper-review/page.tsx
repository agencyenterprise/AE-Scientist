"use client";

import { PaperReviewUpload } from "@/features/paper-review/components/PaperReviewUpload";
import { PaperReviewHistory } from "@/features/paper-review/components/PaperReviewHistory";
import { PageCard } from "@/shared/components/PageCard";

export default function PaperReviewPage() {
  return (
    <div className="flex flex-col gap-6">
      <PageCard>
        <div className="p-6">
          <h1 className="mb-2 text-2xl font-semibold text-white">Paper Review</h1>
          <p className="mb-6 text-slate-400">
            Upload a research paper PDF to get an AI-powered review with scores, strengths,
            weaknesses, and recommendations.
          </p>
          <PaperReviewUpload />
        </div>
      </PageCard>

      <PageCard>
        <div className="p-6">
          <h2 className="mb-4 text-lg font-semibold text-white">Review History</h2>
          <PaperReviewHistory />
        </div>
      </PageCard>
    </div>
  );
}
