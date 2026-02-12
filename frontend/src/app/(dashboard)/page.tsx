import { CreateHypothesisForm } from "@/features/input-pipeline/components/CreateHypothesisForm";
import { ResearchHistoryList } from "@/features/research/components/ResearchHistoryList";
import { GettingStartedCard } from "@/shared/components/GettingStartedCard";
import { PageCard } from "@/shared/components/PageCard";
import { Rocket } from "lucide-react";

export const dynamic = "force-dynamic";

export default async function HomePage() {
  return (
    <div className="flex flex-col gap-6 sm:gap-12">
      <PageCard>
        <div className="relative mx-auto flex max-w-3xl flex-col gap-6 text-center px-4 py-8 sm:gap-10 sm:px-6 sm:py-12">
          <div className="flex flex-col items-center gap-4">
            <span className="inline-flex items-center gap-2 rounded-full border border-sky-500/40 bg-sky-500/15 px-4 py-1 text-xs font-semibold uppercase tracking-[0.3em] text-sky-200">
              <Rocket className="h-3.5 w-3.5" />
              Submit a hypothesis
            </span>
            <h1 className="text-balance text-4xl font-semibold text-white sm:text-5xl">
              What should the AE Scientist run next?
            </h1>
          </div>

          <div className="relative rounded-2xl border border-slate-800/70 bg-slate-950/80 p-4 text-left shadow-[0_20px_60px_-40px_rgba(125,211,252,0.35)] backdrop-blur sm:rounded-[28px] sm:p-6 sm:shadow-[0_30px_80px_-50px_rgba(125,211,252,0.45)]">
            <CreateHypothesisForm />
          </div>

          <p className="text-xs text-slate-500">
            Runs kick off the moment a hypothesis is ready, then experimentation with real-time
            updates across the dashboard.
          </p>

          <GettingStartedCard />
        </div>
      </PageCard>
      <PageCard>
        <ResearchHistoryList />
      </PageCard>
    </div>
  );
}
