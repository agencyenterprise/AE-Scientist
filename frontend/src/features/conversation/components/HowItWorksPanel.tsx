import { cn } from "@/shared/lib/utils";
import { AlertTriangle, BarChart3, Clock4, DollarSign, FileText, GitBranch } from "lucide-react";

const FLOW_STEPS = [
  {
    title: "Design experiments in code",
    detail:
      "Writes training scripts and evaluation loops that can run end-to-end.",
  },
  {
    title: "Agentic tree search",
    detail:
      "Branches into alternative experiment ideas, exploring variations systematically before committing GPU time.",
  },
  {
    title: "Run & analyze",
    detail: "Executes selected experiments, logs metrics, and produces plots as runs complete.",
  },
  {
    title: "Draft manuscript",
    detail: "Compiles findings into a structured paper with figures, tables, and citations.",
  },
];

const BEST_USE_CASES = [
  "Deep learning model evaluation and algorithmic experiments (e.g., regularization, generalization).",
  "Applied ML systems such as pest detection or similar domain-specific perception problems.",
  "Statistical analysis on data-centric questions like label-noise impact on calibration.",
];

const LIMITATIONS = [
  "Prompt-only or API chaining tasks (e.g., “Use the GPT5 API to do X”) that lack executable experiments.",
  "Experiments needing external proprietary services or hardware that the platform cannot access.",
  "Projects requiring human-in-the-loop data collection or wet-lab procedures.",
];

interface HowItWorksPanelProps {
  className?: string;
}

export function HowItWorksPanel({ className }: HowItWorksPanelProps) {
  return (
    <div className={cn("space-y-6 text-sm text-slate-100", className)}>
      <div className="flex items-center gap-2 text-xs uppercase tracking-[0.2em] text-slate-400">
        <GitBranch className="h-4 w-4 text-sky-400" />
        <span>How AE Scientist Runs</span>
      </div>
      <h2 className="mt-2 text-2xl font-semibold text-white">Understand the pipeline</h2>
      <p className="mt-2 text-slate-300">
        AE Scientist automates an end-to-end research workflow, from idea generation to manuscript
        drafting. Use this tab to sanity-check whether your project fits the system&apos;s current
        constraints before launching a run.
      </p>

      <section className="mt-6">
        <h3 className="text-base font-semibold text-white">Standard flow</h3>
        <ol className="mt-3 space-y-3">
          {FLOW_STEPS.map((step, index) => (
            <li
              key={step.title}
              className="rounded-xl border border-slate-800/60 bg-slate-900/40 p-4 shadow-sm"
            >
              <div className="flex items-center gap-3">
                <span className="flex h-6 w-6 items-center justify-center rounded-full bg-sky-500/20 text-xs font-semibold text-sky-300">
                  {index + 1}
                </span>
                <p className="text-sm font-semibold text-white">{step.title}</p>
              </div>
              <p className="mt-2 text-slate-300">{step.detail}</p>
            </li>
          ))}
        </ol>
      </section>

      <section className="mt-6 grid gap-4 md:grid-cols-3">
        <div className="rounded-xl border border-slate-800/60 bg-slate-900/40 p-4">
          <div className="flex items-center gap-2 text-slate-400 text-xs uppercase tracking-widest">
            <Clock4 className="h-4 w-4 text-amber-300" />
            Runtime
          </div>
          <p className="mt-2 text-lg font-semibold text-white">~3 hours</p>
          <p className="text-slate-400 text-sm">Includes queueing, execution, and analysis.</p>
        </div>
        <div className="rounded-xl border border-slate-800/60 bg-slate-900/40 p-4">
          <div className="flex items-center gap-2 text-slate-400 text-xs uppercase tracking-widest">
            <DollarSign className="h-4 w-4 text-emerald-300" />
            Cost
          </div>
          <p className="mt-2 text-lg font-semibold text-white">$20 USD</p>
          <p className="text-slate-400 text-sm">Charged per research run.</p>
        </div>
        <div className="rounded-xl border border-slate-800/60 bg-slate-900/40 p-4">
          <div className="flex items-center gap-2 text-slate-400 text-xs uppercase tracking-widest">
            <FileText className="h-4 w-4 text-sky-300" />
            Deliverables
          </div>
          <p className="mt-2 text-lg font-semibold text-white">PDF + Code + Plots</p>
          <p className="text-slate-400 text-sm">
            Final manuscript, executable notebooks/configs, and generated visualizations.
          </p>
        </div>
      </section>

      <section className="mt-6">
        <h3 className="text-base font-semibold text-white">Best situations to run</h3>
        <ul className="mt-3 space-y-2 text-slate-300">
          {BEST_USE_CASES.map(item => (
            <li key={item} className="flex items-start gap-2">
              <BarChart3 className="mt-0.5 h-4 w-4 text-sky-300" />
              <span>{item}</span>
            </li>
          ))}
        </ul>
      </section>

      <section className="mt-6 rounded-2xl border border-amber-500/30 bg-amber-500/10 p-4">
        <div className="flex items-center gap-2 text-sm font-semibold text-amber-200">
          <AlertTriangle className="h-5 w-5" />
          Know the current limitations
        </div>
        <ul className="mt-3 space-y-2 text-amber-100/90">
          {LIMITATIONS.map(item => (
            <li key={item} className="flex items-start gap-2">
              <span className="mt-0.5 h-2 w-2 rounded-full bg-amber-300/80" />
              <span>{item}</span>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}

