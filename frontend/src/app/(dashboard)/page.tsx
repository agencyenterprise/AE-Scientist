import { CreateHypothesisForm } from "@/features/input-pipeline/components/CreateHypothesisForm";
import { Rocket } from "lucide-react";

export const dynamic = "force-dynamic";

export default async function HomePage() {
  return (
    <div className="relative mx-auto flex max-w-3xl flex-col gap-10 text-center px-6 py-12">
      <div className="flex flex-col items-center gap-4">
        <span className="inline-flex items-center gap-2 rounded-full border border-sky-500/40 bg-sky-500/15 px-4 py-1 text-xs font-semibold uppercase tracking-[0.3em] text-sky-200">
          <Rocket className="h-3.5 w-3.5" />
          Submit a hypothesis
        </span>
        <h1 className="text-balance text-4xl font-semibold text-white sm:text-5xl">
          What should the AI Scientist run next?
        </h1>
        <p className="max-w-2xl text-pretty text-base text-slate-300 sm:text-lg">
          Promote a favorite ideation outcome or craft a brand new research direction. We’ll run the
          experiments and keep you in the loop every step of the way.
        </p>
      </div>

      <div className="relative rounded-[28px] border border-slate-800/70 bg-slate-950/80 p-6 text-left shadow-[0_30px_80px_-50px_rgba(125,211,252,0.45)] backdrop-blur">
        <CreateHypothesisForm />
      </div>

      <p className="text-xs text-slate-500">
        Runs kick off the moment a hypothesis is ready, then experimentation with real-time updates
        across the dashboard.
      </p>
    </div>
  );
}
