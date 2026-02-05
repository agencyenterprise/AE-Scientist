"use client";

import { useState } from "react";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import {
  Menu,
  X,
  MessageSquare,
  FlaskConical,
  BookOpen,
  FileSearch,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useWalletBalance } from "@/shared/hooks/useWalletBalance";
import { cn } from "@/shared/lib/utils";

export function MobileNav() {
  const [open, setOpen] = useState(false);
  const pathname = usePathname();
  const { balanceDollars, isLoading } = useWalletBalance();

  const isConversationsActive = pathname.startsWith("/conversations");
  const isResearchActive = pathname.startsWith("/research");
  const isPaperReviewActive = pathname.startsWith("/paper-review");
  const isHowItWorksActive = pathname.startsWith("/how-it-works");

  const navItems = [
    {
      href: "/how-it-works",
      label: "How it works",
      icon: BookOpen,
      isActive: isHowItWorksActive,
      activeClass: "bg-violet-500/15 text-violet-300",
    },
    {
      href: "/conversations",
      label: "Ideation Queue",
      icon: MessageSquare,
      isActive: isConversationsActive,
      activeClass: "bg-sky-500/15 text-sky-400",
    },
    {
      href: "/research",
      label: "Research",
      icon: FlaskConical,
      isActive: isResearchActive,
      activeClass: "bg-emerald-500/15 text-emerald-400",
    },
    {
      href: "/paper-review",
      label: "Paper Review",
      icon: FileSearch,
      isActive: isPaperReviewActive,
      activeClass: "bg-amber-500/15 text-amber-400",
    },
  ];

  return (
    <DialogPrimitive.Root open={open} onOpenChange={setOpen}>
      <DialogPrimitive.Trigger asChild>
        <button
          className="flex h-9 w-9 items-center justify-center rounded-lg text-slate-400 transition-colors hover:bg-slate-800 hover:text-white md:hidden"
          aria-label="Open navigation menu"
        >
          <Menu className="h-5 w-5" />
        </button>
      </DialogPrimitive.Trigger>

      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0" />
        <DialogPrimitive.Content
          className="fixed inset-y-0 left-0 z-50 flex h-full w-72 flex-col border-r border-slate-800 bg-slate-900 shadow-xl data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:slide-out-to-left data-[state=open]:slide-in-from-left duration-300"
          aria-describedby={undefined}
        >
          <div className="flex items-center justify-between border-b border-slate-800 px-4 py-4">
            <DialogPrimitive.Title className="text-lg font-semibold text-white">
              Menu
            </DialogPrimitive.Title>
            <DialogPrimitive.Close asChild>
              <button
                className="flex h-8 w-8 items-center justify-center rounded-lg text-slate-400 transition-colors hover:bg-slate-800 hover:text-white"
                aria-label="Close navigation menu"
              >
                <X className="h-5 w-5" />
              </button>
            </DialogPrimitive.Close>
          </div>

          <nav className="flex flex-1 flex-col gap-1 p-4">
            {navItems.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                onClick={() => setOpen(false)}
                className={cn(
                  "flex items-center gap-3 rounded-lg px-3 py-3 text-sm font-medium transition-colors",
                  item.isActive
                    ? item.activeClass
                    : "text-slate-400 hover:bg-slate-800 hover:text-white"
                )}
              >
                <item.icon className="h-5 w-5" />
                {item.label}
              </Link>
            ))}
          </nav>

          <div className="border-t border-slate-800 p-4">
            <Link
              href="/billing"
              onClick={() => setOpen(false)}
              className="flex items-center justify-between rounded-lg border border-slate-700/60 bg-slate-800/60 px-4 py-3 transition-colors hover:border-emerald-500/60 hover:bg-slate-800"
            >
              <span className="text-sm text-slate-400">Balance</span>
              <span className="font-semibold text-white">
                {isLoading
                  ? "…"
                  : `$${balanceDollars.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`}
              </span>
            </Link>
          </div>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}
