"use client";

import React, { useCallback } from "react";
import { useRouter, usePathname } from "next/navigation";

import type { Conversation } from "@/lib/api-adapters";

interface SidebarProps {
  conversations: Conversation[];
  selectedConversationId?: number;
  onConversationSelect: (conversation: Conversation) => void;
  onImportClick: () => void;
  isLoading?: boolean;
  isCollapsed?: boolean;
  loadingConversationId?: number; // NEW: Track which conversation is loading
  onLogout?: () => void;
  collapseSidebar: () => void;
}

export function Sidebar({
  conversations,
  selectedConversationId,
  onConversationSelect,
  onImportClick,
  isLoading = false,
  isCollapsed = false,
  loadingConversationId,
  onLogout,
  collapseSidebar,
}: SidebarProps) {
  const router = useRouter();
  const pathname = usePathname();
  const collapseIfMobile = useCallback((): void => {
    if (typeof window !== "undefined" && window.matchMedia("(max-width: 767px)").matches) {
      collapseSidebar();
    }
  }, [collapseSidebar]);
  const openDashboard = useCallback(() => {
    router.push(`/`);
    collapseIfMobile();
  }, [router, collapseIfMobile]);

  const isDashboardActive = pathname === "/";

  const filteredConversations = conversations.sort((a, b) => {
    // Sort by creation date (newest first)
    return new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime();
  });

  if (isCollapsed) {
    return null; // Desktop expand button rendered by container in dashboard layout
  }

  return (
    <div className="h-full bg-background border-r border-border flex flex-col relative">
      {/* Header */}
      <div className="py-4 sticky top-0 z-10 bg-background/80 backdrop-blur supports-[backdrop-filter]:bg-background/70">
        <div className="relative flex items-center justify-center pl-10 sm:pl-0">
          <h1 className="text-lg font-bold text-foreground text-center w-full px-6">
            Judd&apos;s Idea Catalog
          </h1>
        </div>
      </div>

      {/* Dashboard + Import Buttons Row */}
      <div className="p-4 pt-0 border-b border-border">
        <div className={`grid ${isDashboardActive ? "grid-cols-1" : "grid-cols-2"} gap-2`}>
          {!isDashboardActive && (
            <button
              type="button"
              onClick={openDashboard}
              className="btn-secondary w-full py-2"
              title="Go to dashboard"
            >
              <svg className="h-4 w-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0h6"
                />
              </svg>
              Dashboard
            </button>
          )}
          <button
            onClick={() => {
              onImportClick();
              collapseIfMobile();
            }}
            disabled={isLoading}
            className="btn-primary-gradient w-full py-2 px-3"
            title="Import chat"
          >
            {isLoading ? (
              <>
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                Importing...
              </>
            ) : (
              <>
                <svg className="h-4 w-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M12 4v16m8-8H4"
                  />
                </svg>
                Import
              </>
            )}
          </button>
        </div>
      </div>

      {/* Conversations List */}
      <div className="flex-1 overflow-y-auto">
        {filteredConversations.length === 0 ? (
          <div className="p-4 text-center text-muted-foreground">
            {conversations.length === 0 ? (
              <>
                <svg
                  className="mx-auto h-12 w-12 text-muted-foreground mb-2"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-3.582 8-8 8a8.955 8.955 0 01-2.011-.235l-3.678 1.47a1 1 0 01-1.31-1.31l1.47-3.678A8.955 8.955 0 013 12a8 8 0 018-8c4.418 0 8 3.582 8 8z"
                  />
                </svg>
                <p className="text-sm">No conversations yet</p>
                <p className="text-xs text-muted-foreground mt-1">
                  Click &quot;Import Chat&quot; to get started
                </p>
              </>
            ) : (
              <p className="text-sm">No conversations match your search</p>
            )}
          </div>
        ) : (
          <div className="divide-y divide-border/60">
            {filteredConversations.map(conversation => {
              const isSelected = selectedConversationId === conversation.id;
              const isLoadingThis = loadingConversationId === conversation.id;

              return (
                <div
                  key={conversation.id}
                  onClick={() => onConversationSelect(conversation)}
                  className={`px-4 py-2 cursor-pointer transition-all duration-150 relative hover:bg-muted ${
                    isSelected
                      ? "bg-primary/10 border-r-2 border-primary"
                      : ""
                  }`}
                >
                  {/* Loading indicator overlay */}
                  {isLoadingThis && (
                    <div className="absolute inset-0 bg-background/70 flex items-center justify-center">
                      <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-primary"></div>
                    </div>
                  )}

                  <div className="flex items-start justify-between">
                    <h3
                      className={`font-medium truncate text-sm flex items-center text-foreground ${isLoadingThis ? "opacity-50" : ""}`}
                    >
                      <span className="truncate">{conversation.title}</span>
                    </h3>
                  </div>
                  <div className="flex justify-between items-center mt-1">
                    <span className={`text-xs text-muted-foreground ${isLoadingThis ? "opacity-50" : ""}`}>
                      {conversation.userName}
                    </span>
                    <span className={`text-xs text-muted-foreground ${isLoadingThis ? "opacity-50" : ""}`}>
                      {new Date(conversation.createdAt).toLocaleDateString()}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="p-4 border-t border-border">
        <div className="flex justify-between items-center">
          <p className="text-xs text-muted-foreground">
            {conversations.length} conversation{conversations.length !== 1 ? "s" : ""}
          </p>
          {onLogout && (
            <button
              onClick={onLogout}
              className="text-xs text-muted-foreground hover:text-foreground hover:bg-muted px-2 py-1 rounded-md transition-all duration-200 cursor-pointer"
            >
              Logout
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
