"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";

import { Sidebar } from "@/components/layout/Sidebar";
import { ImportModal } from "@/components/ImportModal";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { config } from "@/lib/config";
import type { Conversation } from "@/lib/api-adapters";
import { convertApiConversationList } from "@/lib/api-adapters";
import {
  DashboardContext,
  type LinearFilter,
  type SortDir,
  type SortKey,
} from "./DashboardContext";
import { useAuth } from "@/hooks/useAuth";

interface DashboardLayoutProps {
  children: React.ReactNode;
}

export default function DashboardLayout({ children }: DashboardLayoutProps) {
  const router = useRouter();
  const pathname = usePathname();
  const { logout } = useAuth();

  // Shared state for all dashboard pages
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [isImportModalOpen, setIsImportModalOpen] = useState(false);
  const [isImporting, setIsImporting] = useState(false);
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState<boolean>(() => {
    if (typeof window !== "undefined") {
      return window.matchMedia("(max-width: 767px)").matches;
    }
    return false;
  });
  const [linearFilter, setLinearFilter] = useState<LinearFilter>("all");
  const [sortKey, setSortKey] = useState<SortKey>("updated");
  const [sortDir, setSortDir] = useState<SortDir>("desc");

  // Determine selected conversation ID from pathname
  const selectedConversationId = pathname.startsWith("/conversations/")
    ? (() => {
        const idString = pathname.split("/")[2];
        return idString ? parseInt(idString, 10) || undefined : undefined;
      })()
    : undefined;

  const loadConversations = useCallback(async (): Promise<void> => {
    try {
      const response = await fetch(`${config.apiUrl}/conversations?limit=500&offset=0`, {
        credentials: "include", // Include authentication cookies
      });
      if (response.ok) {
        const apiResponse = await response.json();
        const data = convertApiConversationList(apiResponse);
        setConversations(data);
      } else if (response.status === 401) {
        // Authentication required - user will be redirected by ProtectedRoute
        // silence console in prod/CI
      }
    } catch {
      // silence error in prod/CI
    }
  }, []);

  // Load conversations on mount
  useEffect(() => {
    loadConversations();
  }, [loadConversations]);

  const handleConversationSelect = async (conversation: Conversation): Promise<void> => {
    // Don't navigate if already selected
    if (selectedConversationId === conversation.id) {
      return;
    }

    // Navigate to conversation page
    router.push(`/conversations/${conversation.id}`);
    collapseIfMobile();
  };

  const toggleSidebar = (): void => {
    setIsSidebarCollapsed(!isSidebarCollapsed);
  };

  const collapseIfMobile = (): void => {
    if (typeof window !== "undefined" && window.matchMedia("(max-width: 767px)").matches) {
      setIsSidebarCollapsed(true);
    }
  };

  // Context value for child components
  const dashboardContextValue = {
    conversations,
    selectConversation: handleConversationSelect,
    refreshConversations: loadConversations,
    openImportModal: () => setIsImportModalOpen(true),
    linearFilter,
    setLinearFilter,
    isSidebarCollapsed,
    sortKey,
    setSortKey,
    sortDir,
    setSortDir,
  };

  return (
    <ProtectedRoute>
      <DashboardContext.Provider value={dashboardContextValue}>
        <div className="relative h-screen flex">
          {/* Mobile overlay when sidebar is open */}
          {!isSidebarCollapsed && (
            <div className="md:hidden fixed inset-0 z-30 bg-black/30" onClick={toggleSidebar} />
          )}

          {/* Unified toggle button (mobile + desktop) */}
          <button
            type="button"
            aria-label={isSidebarCollapsed ? "Open menu" : "Close menu"}
            onClick={toggleSidebar}
            className="fixed left-3 top-2 z-50 bg-white border border-gray-300 rounded-full shadow px-3 py-3 md:px-2 md:py-2 text-gray-700 hover:bg-gray-100 active:bg-gray-200"
            title={isSidebarCollapsed ? "Open menu" : "Close menu"}
          >
            <svg
              className="w-5 h-5 md:w-4 md:h-4"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d={isSidebarCollapsed ? "M4 6h16M4 12h16M4 18h16" : "M6 18L18 6M6 6l12 12"}
              />
            </svg>
          </button>

          {/* Sidebar container - off-canvas on mobile, static on desktop */}
          <div className="flex-shrink-0">
            <div
              className={`group fixed inset-y-0 left-0 z-40 w-72 transform transition-transform duration-300 md:static md:h-screen ${
                isSidebarCollapsed ? "-translate-x-full md:w-0" : "translate-x-0 md:w-80"
              }`}
            >
              {/* Desktop chevron handles removed in favor of unified toggle button */}

              <Sidebar
                conversations={conversations}
                selectedConversationId={selectedConversationId}
                onConversationSelect={handleConversationSelect}
                onImportClick={() => setIsImportModalOpen(true)}
                isLoading={isImporting}
                isCollapsed={isSidebarCollapsed}
                onLogout={logout}
                collapseSidebar={() => setIsSidebarCollapsed(true)}
              />
            </div>
          </div>

          {/* Main Content */}
          <div className="flex-1 min-h-0 overflow-hidden">{children}</div>

          {/* Import Modal */}
          <ImportModal
            isOpen={isImportModalOpen}
            onClose={() => setIsImportModalOpen(false)}
            onImportStart={() => setIsImporting(true)}
            onImportEnd={() => setIsImporting(false)}
          />
        </div>
      </DashboardContext.Provider>
    </ProtectedRoute>
  );
}
