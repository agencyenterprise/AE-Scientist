"use client";

import { UserProfileDropdown } from "@/features/user-profile/components/UserProfileDropdown";
import { useAuth } from "@/shared/hooks/useAuth";
import { useWalletBalance } from "@/shared/hooks/useWalletBalance";
import { MessageSquare, FlaskConical, BookOpen, FileSearch } from "lucide-react";
import { MobileNav } from "./MobileNav";
import Link from "next/link";
import { usePathname } from "next/navigation";

export function Header() {
  const { user } = useAuth();
  const pathname = usePathname();
  const { balanceDollars, isLoading } = useWalletBalance();

  const isConversationsActive = pathname.startsWith("/conversations");
  const isResearchActive = pathname.startsWith("/research");
  const isPaperReviewActive = pathname.startsWith("/paper-review");
  const isHowItWorksActive = pathname.startsWith("/how-it-works");

  return (
    <header className="border-b border-slate-800 bg-slate-900/70 backdrop-blur">
      <div className="mx-auto flex w-full max-w-7xl items-center justify-between px-4 py-4 md:px-8">
        <div className="flex items-center gap-4 md:gap-8">
          {user && <MobileNav />}
          <div className="flex items-center gap-2">
            <Link href="/" className="text-lg font-semibold text-white">
              AE Scientist
            </Link>
            <span className="hidden text-sm text-slate-500 sm:inline">·</span>
            <span className="hidden text-sm text-slate-500 sm:inline">
              Built by{" "}
              <a
                href="https://ae.studio"
                target="_blank"
                rel="noopener noreferrer"
                className="!text-slate-500 hover:underline"
              >
                AE Studio
              </a>
            </span>
          </div>
          {user && (
            <nav className="hidden items-center gap-1 md:flex">
              <Link
                href="/how-it-works"
                className={`flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                  isHowItWorksActive
                    ? "bg-violet-500/15 text-violet-300"
                    : "text-slate-400 hover:bg-slate-800 hover:text-white"
                }`}
              >
                <BookOpen className="h-4 w-4" />
                How it works
              </Link>
              <Link
                href="/conversations"
                className={`flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                  isConversationsActive
                    ? "bg-sky-500/15 text-sky-400"
                    : "text-slate-400 hover:bg-slate-800 hover:text-white"
                }`}
              >
                <MessageSquare className="h-4 w-4" />
                Ideation Queue
              </Link>
              <Link
                href="/research"
                className={`flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                  isResearchActive
                    ? "bg-emerald-500/15 text-emerald-400"
                    : "text-slate-400 hover:bg-slate-800 hover:text-white"
                }`}
              >
                <FlaskConical className="h-4 w-4" />
                Research
              </Link>
              <Link
                href="/paper-review"
                className={`flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                  isPaperReviewActive
                    ? "bg-amber-500/15 text-amber-400"
                    : "text-slate-400 hover:bg-slate-800 hover:text-white"
                }`}
              >
                <FileSearch className="h-4 w-4" />
                Paper Review
              </Link>
            </nav>
          )}
        </div>
        <div className="flex items-center gap-2 md:gap-4">
          {user && (
            <Link
              href="/billing"
              className="hidden items-center gap-2 rounded-lg border border-slate-700/60 bg-slate-800/60 px-3 py-1.5 text-sm text-slate-200 transition-colors hover:border-emerald-500/60 hover:bg-slate-800 md:flex"
            >
              <span className="text-xs uppercase tracking-wide text-slate-400">Balance</span>
              <span className="font-semibold text-white">
                {isLoading
                  ? "…"
                  : `$${balanceDollars.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`}
              </span>
            </Link>
          )}
          <UserProfileDropdown />
        </div>
      </div>
    </header>
  );
}
