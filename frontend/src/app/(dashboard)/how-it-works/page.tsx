"use client";

import { BestPaperShowcase } from "@/features/conversation/components/BestPaperShowcase";
import { HowItWorksPanel } from "@/features/conversation/components/HowItWorksPanel";
import { PageCard } from "@/shared/components/PageCard";

export default function HowItWorksPage() {
  return (
    <PageCard>
      <div className="relative z-[1] space-y-4 p-3 sm:space-y-6 sm:p-6">
        <HowItWorksPanel className="rounded-xl sm:rounded-2xl border border-slate-800 bg-slate-950/60 p-4 sm:p-6" />
        <BestPaperShowcase className="rounded-xl sm:rounded-2xl border border-slate-800 bg-slate-950/60 p-4 sm:p-6" />
      </div>
    </PageCard>
  );
}
