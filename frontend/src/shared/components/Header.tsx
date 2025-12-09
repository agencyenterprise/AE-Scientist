"use client";

import { UserProfileDropdown } from "@/features/user-profile/components/UserProfileDropdown";
import { useAuth } from "@/shared/hooks/useAuth";
import { MessageSquare, FlaskConical } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

export function Header() {
  const { user } = useAuth();
  const pathname = usePathname();

  const isConversationsActive = pathname.startsWith("/conversations");
  const isResearchActive = pathname.startsWith("/research");

  return (
    <header className="border-b border-slate-800 bg-slate-900/70 backdrop-blur">
      <div className="mx-auto flex w-full max-w-7xl items-center justify-between px-8 py-4">
        <div className="flex items-center gap-8">
          <Link href="/" className="text-lg font-semibold text-white">
            AI Scientist Orchestrator
          </Link>
          {user && (
            <nav className="flex items-center gap-1">
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
            </nav>
          )}
        </div>
        <UserProfileDropdown />
      </div>
    </header>
  );
}
