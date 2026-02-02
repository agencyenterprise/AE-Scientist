"use client";

import { useState, useCallback } from "react";
import { PaperReviewUpload } from "@/features/paper-review/components/PaperReviewUpload";
import { PaperReviewHistory } from "@/features/paper-review/components/PaperReviewHistory";
import { PageCard } from "@/shared/components/PageCard";

export default function PaperReviewPage() {
  // Counter to trigger history refresh when user starts a new review
  const [historyRefreshKey, setHistoryRefreshKey] = useState(0);

  const handleStartNewReview = useCallback(() => {
    // Increment key to trigger PaperReviewHistory to refetch all reviews
    setHistoryRefreshKey(prev => prev + 1);
  }, []);

  return (
    <div className="flex flex-col gap-6">
      <PageCard>
        <div className="p-6">
          <h1 className="mb-2 text-2xl font-semibold text-white">Paper Review</h1>
          <p className="mb-6 text-slate-400">
            Upload a research paper PDF to get an AI-powered review with scores, strengths,
            weaknesses, and recommendations.
          </p>
          <PaperReviewUpload onStartNewReview={handleStartNewReview} />
        </div>
      </PageCard>

      <PageCard>
        <div className="p-6">
          <h2 className="mb-4 text-lg font-semibold text-white">Review History</h2>
          <PaperReviewHistory refreshKey={historyRefreshKey} />
        </div>
      </PageCard>
    </div>
  );
}
