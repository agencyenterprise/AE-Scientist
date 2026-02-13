"use client";

import { UserButton } from "@clerk/nextjs";
import { FileText } from "lucide-react";
import Link from "next/link";

export function Header() {
  return (
    <header className="glass-effect sticky top-0 z-50 border-b border-slate-800/50">
      <div className="container mx-auto max-w-5xl px-4">
        <div className="flex h-16 items-center justify-between">
          <Link
            href="/dashboard"
            className="flex items-center gap-2 text-white hover:text-sky-400 transition-colors"
          >
            <FileText className="h-5 w-5 sm:h-6 sm:w-6" />
            <span className="font-semibold text-base sm:text-lg">
              AE Paper Review
            </span>
          </Link>

          <div className="flex items-center gap-4">
            <UserButton
              appearance={{
                elements: {
                  avatarBox: "h-8 w-8",
                  userButtonPopoverCard: "bg-slate-900 border-slate-800",
                  userButtonPopoverActionButton:
                    "text-slate-300 hover:bg-slate-800",
                  userButtonPopoverActionButtonText: "text-slate-300",
                  userButtonPopoverFooter: "hidden",
                },
              }}
            />
          </div>
        </div>
      </div>
    </header>
  );
}
