"use client";

import { BestPaperShowcase } from "@/features/conversation/components/BestPaperShowcase";
import { HowItWorksPanel } from "@/features/conversation/components/HowItWorksPanel";
import { PageCard } from "@/shared/components/PageCard";

export default function HowItWorksPage() {
  return (
    <PageCard>
      <div className="relative z-[1] space-y-6 p-6">
        <HowItWorksPanel className="rounded-2xl border border-slate-800 bg-slate-950/60 p-6" />
        <BestPaperShowcase className="rounded-2xl border border-slate-800 bg-slate-950/60 p-6" />
      </div>
    </PageCard>
  );
}
