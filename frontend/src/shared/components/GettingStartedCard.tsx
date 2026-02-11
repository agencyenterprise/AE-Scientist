"use client";

import { useAuth } from "@/shared/hooks/useAuth";
import { MessageSquare, FlaskConical, Sparkles } from "lucide-react";
import Link from "next/link";

const SUPPORT_EMAIL = process.env.NEXT_PUBLIC_SUPPORT_EMAIL || "james.bowler@ae.studio";

function buildFreeTrialMailto(userEmail?: string): string {
  const body = `Hi,

I'm interested in trying AE Scientist. Here are my details:

Account email: ${userEmail || "[your email]"}

Use case:

[Please describe your research interest or use case]

Thanks!`;
  return `mailto:${SUPPORT_EMAIL}?subject=${encodeURIComponent("Free Trial Request - AE Scientist")}&body=${encodeURIComponent(body)}`;
}

export function GettingStartedCard() {
  const { user } = useAuth();
  const freeTrialMailto = buildFreeTrialMailto(user?.email);

  if (!user) return null;

  return (
    <div className="rounded-2xl border border-sky-500/20 bg-gradient-to-br from-sky-950/40 to-slate-900/60 p-5">
      <div className="flex items-center gap-2 text-sm font-semibold text-sky-400">
        <Sparkles className="h-4 w-4" />
        Getting started
      </div>

      <div className="mt-4 space-y-3">
        <div className="flex gap-3">
          <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-sky-500/20 text-xs font-semibold text-sky-300">
            1
          </div>
          <div>
            <div className="flex items-center gap-2">
              <MessageSquare className="h-4 w-4 text-sky-400" />
              <span className="text-sm font-medium text-white">Refine your idea</span>
              <span className="rounded bg-slate-800 px-1.5 py-0.5 text-[10px] text-slate-400">
                &lt;$1
              </span>
            </div>
            <p className="mt-1 text-xs text-slate-400">
              Describe your hypothesis below. Chat with an AI to shape it into a concrete research
              plan.
            </p>
          </div>
        </div>

        <div className="flex gap-3">
          <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-emerald-500/20 text-xs font-semibold text-emerald-300">
            2
          </div>
          <div className="text-left">
            <div className="flex items-center gap-2">
              <FlaskConical className="h-4 w-4 text-emerald-400" />
              <span className="text-sm font-medium text-white">Launch the pipeline</span>
              <span className="rounded bg-slate-800 px-1.5 py-0.5 text-[10px] text-slate-400">
                ~$25 · 4-6h
              </span>
            </div>
            <p className="mt-1 text-xs text-slate-400">
              When ready, launch a full research run. Cost varies by the hardware you select.
            </p>
            <p className="mt-1 text-xs text-slate-400">
              If your balance goes negative, results are locked until you add credits.
            </p>
          </div>
        </div>
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-2">
        <Link
          href="/billing"
          className="rounded-lg bg-sky-600 px-3.5 py-1.5 text-sm font-medium text-white transition hover:bg-sky-500"
        >
          Add Credits
        </Link>
        <a
          href={freeTrialMailto}
          className="rounded-lg px-3.5 py-1.5 text-sm font-medium text-slate-400 transition hover:bg-slate-800 hover:text-slate-200"
        >
          Request Free Trial
        </a>
      </div>
    </div>
  );
}
