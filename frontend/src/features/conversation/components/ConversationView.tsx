"use client";

import { ConversationHeader } from "@/features/conversation/components/ConversationHeader";
import { ConversationProvider } from "@/features/conversation/context/ConversationContext";
import { ProjectDraftTab } from "@/features/project-draft/components/ProjectDraftTab";
import type { ConversationCostResponse, ConversationDetail } from "@/types";
import { useState, useEffect } from "react";
import {
  MessageCircle,
  MessageSquare,
  Lightbulb,
  Menu,
  Rocket,
  FlaskConical,
  BookOpen,
  FileSearch,
} from "lucide-react";
import { cn } from "@/shared/lib/utils";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useWalletBalance } from "@/shared/hooks/useWalletBalance";

interface ConversationViewProps {
  conversation?: ConversationDetail;
  isLoading?: boolean;
  onConversationDeleted?: () => void;
  onTitleUpdated?: (updatedConversation: ConversationDetail) => void;
  onSummaryGenerated?: (summary: string) => void;
  expandImportedChat?: boolean;
  costDetails: ConversationCostResponse | null;
  onRefreshCostDetails: () => void;
}

export function ConversationView({
  conversation,
  isLoading = false,
  onConversationDeleted,
  onTitleUpdated,
  expandImportedChat = false,
  costDetails,
  onRefreshCostDetails,
}: ConversationViewProps) {
  const pathname = usePathname();
  const [showConversation, setShowConversation] = useState(expandImportedChat);
  const [showProjectDraft, setShowProjectDraft] = useState(true);
  const [mobileProjectView, setMobileProjectView] = useState<"chat" | "draft">(() =>
    pathname.startsWith("/ideation-queue/") ? "chat" : "draft"
  );
  const [hasIdeaUpdate, setHasIdeaUpdate] = useState(false);
  const [showMobileNav, setShowMobileNav] = useState(false);
  const [isTabSwitcherVisible, setIsTabSwitcherVisible] = useState(true);
  const [tabSwitcherElement, setTabSwitcherElement] = useState<HTMLDivElement | null>(null);
  const { balanceDollars, isLoading: isBalanceLoading } = useWalletBalance();

  const isIdeationQueueActive = pathname.startsWith("/ideation-queue");
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
      href: "/ideation-queue",
      label: "Ideation Queue",
      icon: MessageSquare,
      isActive: isIdeationQueueActive,
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

  // Track tab switcher visibility to hide FABs when it's visible
  useEffect(() => {
    if (!tabSwitcherElement) return;

    const observer = new IntersectionObserver(
      entries => {
        const entry = entries[0];
        if (entry) {
          const isVisible = entry.intersectionRatio >= 0.5;
          setIsTabSwitcherVisible(isVisible);
        }
      },
      { threshold: 0.5 }
    );

    observer.observe(tabSwitcherElement);
    return () => observer.disconnect();
  }, [tabSwitcherElement]);

  // Handler for when the mobile view changes - clear update indicator when viewing idea
  const handleMobileViewChange = (view: "chat" | "draft") => {
    setMobileProjectView(view);
    if (view === "draft") {
      setHasIdeaUpdate(false);
    }
  };

  // Handler for when idea is updated - show indicator if not viewing idea on mobile
  const handleIdeaUpdated = () => {
    if (mobileProjectView === "chat") {
      setHasIdeaUpdate(true);
    }
  };

  // Handler for launch research FAB - switch to Idea tab and scroll to bottom
  const handleLaunchResearchClick = () => {
    handleMobileViewChange("draft");
    // Small delay to allow view switch, then scroll to bottom
    setTimeout(() => {
      window.scrollTo({ top: document.body.scrollHeight, behavior: "smooth" });
    }, 100);
  };

  const viewMode: "chat" | "split" | "project" =
    showConversation && showProjectDraft ? "split" : showConversation ? "chat" : "project";

  const handleViewModeChange = (mode: "chat" | "split" | "project"): void => {
    if (mode === "chat") {
      setShowConversation(true);
      setShowProjectDraft(false);
    } else if (mode === "project") {
      setShowConversation(false);
      setShowProjectDraft(true);
    } else {
      setShowConversation(true);
      setShowProjectDraft(true);
    }
  };

  if (isLoading) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-[var(--primary)] mx-auto mb-4"></div>
          <p className="text-muted-foreground">Loading conversation...</p>
        </div>
      </div>
    );
  }

  if (!conversation) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center max-w-md">
          <MessageCircle className="mx-auto h-24 w-24 text-muted-foreground mb-4" strokeWidth={1} />
          <h2 className="text-xl font-medium text-foreground mb-2">
            AE Scientist - AI Research Generator
          </h2>
          <p className="text-muted-foreground mb-4">
            Transform imported conversations into Data Science research
          </p>
          <p className="text-sm text-muted-foreground">
            Select a conversation from the sidebar or import a new one to get started.
          </p>
        </div>
      </div>
    );
  }

  return (
    <ConversationProvider>
      <>
        <div className="flex flex-col md:h-[calc(100vh-180px)] md:overflow-hidden">
          <ConversationHeader
            conversation={conversation}
            onConversationDeleted={onConversationDeleted}
            onTitleUpdated={onTitleUpdated}
            viewMode={viewMode}
            onViewModeChange={handleViewModeChange}
            costDetails={costDetails}
          />

          {/* Mobile Tab Switcher - Segmented control at top, only on mobile */}
          <div
            ref={setTabSwitcherElement}
            className="flex-shrink-0 flex md:hidden border-b border-slate-800 bg-slate-900/80"
          >
            <button
              onClick={() => handleMobileViewChange("chat")}
              className={cn(
                "flex-1 flex items-center justify-center gap-2 py-3 text-sm font-medium transition-colors border-b-2",
                mobileProjectView === "chat"
                  ? "text-sky-400 border-sky-400 bg-sky-500/10"
                  : "text-slate-400 border-transparent hover:text-slate-300"
              )}
            >
              <MessageSquare className="h-4 w-4" />
              Chat
            </button>
            <button
              onClick={() => handleMobileViewChange("draft")}
              className={cn(
                "flex-1 flex items-center justify-center gap-2 py-3 text-sm font-medium transition-colors border-b-2",
                mobileProjectView === "draft"
                  ? "text-amber-400 border-amber-400 bg-amber-500/10"
                  : "text-slate-400 border-transparent hover:text-slate-300"
              )}
            >
              <div className="relative flex items-center gap-2">
                <Lightbulb className="h-4 w-4" />
                Idea
                {hasIdeaUpdate && (
                  <span className="h-2 w-2 rounded-full bg-amber-400 animate-pulse" />
                )}
              </div>
            </button>
          </div>

          {/* Dynamic Content Area - Flexbox layout for smart space allocation */}
          <div className="flex-1 md:min-h-0 md:overflow-hidden">
            <ProjectDraftTab
              conversation={conversation}
              mobileView={mobileProjectView}
              onMobileViewChange={handleMobileViewChange}
              onAnswerFinish={onRefreshCostDetails}
              onIdeaUpdated={handleIdeaUpdated}
            />
          </div>
        </div>

        {/* Floating buttons - Mobile only, hidden when tab switcher is visible */}
        {!isTabSwitcherVisible && (
          <>
            {/* Floating Navigation Menu Button - Left side, at top */}
            <button
              onClick={() => setShowMobileNav(!showMobileNav)}
              className={cn(
                "fixed top-2 left-2 z-[9999] flex md:hidden",
                "h-10 w-10 items-center justify-center rounded-full shadow-lg",
                "bg-slate-700 hover:bg-slate-600 text-white border border-slate-600",
                "transition-all duration-200 active:scale-95"
              )}
              aria-label="Open navigation"
            >
              <Menu className="h-5 w-5" />
            </button>

            {/* Floating Nav Menu Popup - appears below button */}
            {showMobileNav && (
              <div
                className="fixed top-14 left-2 z-[9999] md:hidden flex flex-col gap-1 p-2 rounded-xl bg-slate-800 border border-slate-700 shadow-xl min-w-[200px]"
                role="menu"
              >
                {navItems.map(item => (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={cn(
                      "flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors",
                      item.isActive
                        ? item.activeClass
                        : "text-slate-300 hover:bg-slate-700 hover:text-white"
                    )}
                    onClick={() => setShowMobileNav(false)}
                  >
                    <item.icon className="h-4 w-4" />
                    {item.label}
                  </Link>
                ))}
                <div className="border-t border-slate-700 mt-1 pt-1">
                  <Link
                    href="/billing"
                    onClick={() => setShowMobileNav(false)}
                    className="flex items-center justify-between px-3 py-2 rounded-lg text-sm transition-colors hover:bg-slate-700"
                  >
                    <span className="text-slate-400">Balance</span>
                    <span className="font-semibold text-white">
                      {isBalanceLoading
                        ? "…"
                        : `$${balanceDollars.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`}
                    </span>
                  </Link>
                </div>
              </div>
            )}

            {/* Floating Action Button - Right side, at top, for Chat/Idea switching */}
            <button
              onClick={() =>
                handleMobileViewChange(mobileProjectView === "chat" ? "draft" : "chat")
              }
              className={cn(
                "fixed top-2 right-2 z-[9999] flex md:hidden",
                "h-10 w-10 items-center justify-center rounded-full shadow-lg",
                "transition-all duration-200 active:scale-95",
                mobileProjectView === "chat"
                  ? "bg-amber-500 hover:bg-amber-400 text-slate-900"
                  : "bg-sky-500 hover:bg-sky-400 text-white"
              )}
              aria-label={
                mobileProjectView === "chat" ? "Switch to Idea view" : "Switch to Chat view"
              }
            >
              {mobileProjectView === "chat" ? (
                <Lightbulb className="h-5 w-5" />
              ) : (
                <MessageSquare className="h-5 w-5" />
              )}
              {/* Update badge - shows when idea updated while viewing chat */}
              {hasIdeaUpdate && mobileProjectView === "chat" && (
                <span className="absolute -top-1 -right-1 flex h-5 w-5 items-center justify-center">
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-amber-300 opacity-75" />
                  <span className="relative inline-flex h-4 w-4 rounded-full bg-amber-200 border-2 border-amber-500" />
                </span>
              )}
            </button>

            {/* Floating Action Button - Launch Research, below the view switcher */}
            <button
              onClick={handleLaunchResearchClick}
              className={cn(
                "fixed top-14 right-2 z-[9999] flex md:hidden",
                "h-10 w-10 items-center justify-center rounded-full shadow-lg",
                "bg-emerald-500 hover:bg-emerald-400 text-white",
                "transition-all duration-200 active:scale-95"
              )}
              aria-label="Go to Launch Research"
            >
              <Rocket className="h-5 w-5" />
            </button>
          </>
        )}
      </>
    </ConversationProvider>
  );
}
