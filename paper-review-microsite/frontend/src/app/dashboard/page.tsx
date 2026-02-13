"use client";

import { useState } from "react";

import { PaperReviewUpload } from "@/features/paper-review/components/PaperReviewUpload";
import { PaperReviewHistory } from "@/features/paper-review/components/PaperReviewHistory";
import { PaperReviewHowItWorks } from "@/features/paper-review/components/PaperReviewHowItWorks";

export default function DashboardPage() {
  const [historyRefreshKey, setHistoryRefreshKey] = useState(0);

  const handleReviewStarted = () => {
    setHistoryRefreshKey((prev) => prev + 1);
  };

  return (
    <div className="flex flex-col gap-4 sm:gap-6">
      <div className="card-container p-4 sm:p-6">
        <h1 className="text-xl sm:text-2xl font-bold text-white mb-4 sm:mb-6">
          AE Paper Review
        </h1>
        <PaperReviewUpload onReviewStarted={handleReviewStarted} />
        <PaperReviewHowItWorks className="mt-4 sm:mt-6" />
      </div>

      <div className="card-container p-4 sm:p-6">
        <h2 className="text-lg sm:text-xl font-semibold text-white mb-3 sm:mb-4">
          Review History
        </h2>
        <PaperReviewHistory refreshKey={historyRefreshKey} />
      </div>
    </div>
  );
}
