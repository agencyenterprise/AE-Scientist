"use client";

import { NarrativePageLoading } from "@/features/narrator/components/NarrativePageLoading";
import { NarrativeSystemBoundary } from "@/features/narrator/components/NarrativeResearchPage";
import { Suspense } from "react";

export default function Layout({ children }: { children: React.ReactNode }) {
  return (
    <Suspense fallback={<NarrativePageLoading />}>
      <NarrativeSystemBoundary />

      {children}
    </Suspense>
  );
}
