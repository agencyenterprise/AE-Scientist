"use client";

import { useState, useCallback } from "react";
import { PaperReviewUpload } from "@/features/paper-review/components/PaperReviewUpload";
import { PaperReviewHistory } from "@/features/paper-review/components/PaperReviewHistory";
import { PaperReviewHowItWorks } from "@/features/paper-review/components/PaperReviewHowItWorks";
import { PageCard } from "@/shared/components/PageCard";

export default function PaperReviewPage() {
  // Counter to trigger history refresh when user starts a new review
  const [historyRefreshKey, setHistoryRefreshKey] = useState(0);

  const handleStartNewReview = useCallback(() => {
    // Increment key to trigger PaperReviewHistory to refetch all reviews
    setHistoryRefreshKey(prev => prev + 1);
  }, []);

  return (
    <div className="flex flex-col gap-4 sm:gap-6">
      <PageCard>
        <div className="p-4 sm:p-6">
          <h1 className="mb-2 text-xl font-semibold text-white sm:text-2xl">Paper Review</h1>
          <p className="mb-4 text-sm text-slate-400 sm:mb-6 sm:text-base">
            Upload a research paper PDF to get an AI-powered review with scores, strengths,
            weaknesses, and recommendations.
          </p>
          <PaperReviewUpload onStartNewReview={handleStartNewReview} />

          <PaperReviewHowItWorks className="mt-4 sm:mt-6" />
        </div>
      </PageCard>

      <PageCard>
        <div className="p-4 sm:p-6">
          <h2 className="mb-3 text-base font-semibold text-white sm:mb-4 sm:text-lg">
            Review History
          </h2>
          <PaperReviewHistory refreshKey={historyRefreshKey} />
        </div>
      </PageCard>
    </div>
  );
}
