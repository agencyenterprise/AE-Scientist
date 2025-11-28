import { Header } from "@/shared/components/Header";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "AI Scientist Orchestrator",
  description:
    "Monitor AI scientist hypotheses, runs, validations, and artifacts powered by MongoDB state.",
};

export const dynamic = "force-dynamic";

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col">
      <Header />
      <main className="flex-1 px-4 py-6 sm:px-8">
        <div className="mx-auto flex w-full max-w-7xl flex-col gap-12">
          <section className="relative overflow-hidden rounded-[2.75rem] border border-slate-800/80 bg-slate-950/70 shadow-[0_50px_140px_-60px_rgba(14,165,233,0.9)]">
            <div className="pointer-events-none absolute -left-[20%] -top-[35%] h-[420px] w-[420px] rounded-full bg-sky-500/20 blur-3xl" />
            <div className="pointer-events-none absolute -right-[25%] top-1/3 h-[360px] w-[360px] rounded-full bg-indigo-500/20 blur-3xl" />
            {children}
          </section>
        </div>
      </main>
    </div>
  );
}
