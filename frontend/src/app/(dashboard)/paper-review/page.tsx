"use client";

import { useState, useCallback } from "react";
import { PaperReviewUpload } from "@/features/paper-review/components/PaperReviewUpload";
import { PaperReviewHistory } from "@/features/paper-review/components/PaperReviewHistory";
import { PaperReviewHowItWorks } from "@/features/paper-review/components/PaperReviewHowItWorks";
import { PaperReviewOverview } from "@/features/paper-review/components/PaperReviewOverview";
import { PageCard } from "@/shared/components/PageCard";

export default function PaperReviewPage() {
  // Counter to trigger history refresh when user starts a new review
  const [historyRefreshKey, setHistoryRefreshKey] = useState(0);
  const handleStartNewReview = useCallback(() => {
    setHistoryRefreshKey(prev => prev + 1);
  }, []);

  return (
    <div className="flex flex-col gap-4 sm:gap-6">
      {/* Overview */}
      <PageCard>
        <div className="p-4 sm:p-6">
          <PaperReviewOverview />
        </div>
      </PageCard>

      {/* Upload form */}
      <PageCard>
        <div className="p-4 sm:p-6">
          <h2 className="mb-4 text-lg font-semibold text-white">Submit Your Paper</h2>
          <PaperReviewUpload onStartNewReview={handleStartNewReview} />
        </div>
      </PageCard>

      {/* How it works */}
      <PageCard>
        <div className="p-4 sm:p-6">
          <PaperReviewHowItWorks />
        </div>
      </PageCard>

      {/* History */}
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
