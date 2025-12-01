"use client";

import { ConversationHeader } from "@/features/conversation/components/ConversationHeader";
import { ConversationProvider } from "@/features/conversation/context/ConversationContext";
import { ProjectDraftTab } from "@/features/project-draft/components/ProjectDraftTab";
import type { ConversationDetail } from "@/types";
import React, { useEffect, useState } from "react";
import { MessageCircle } from "lucide-react";
import { apiFetch } from "@/shared/lib/api-client";

interface ConversationViewProps {
  conversation?: ConversationDetail;
  isLoading?: boolean;
  onConversationDeleted?: () => void;
  onTitleUpdated?: (updatedConversation: ConversationDetail) => void;
  onSummaryGenerated?: (summary: string) => void;
  onConversationLocked?: () => void;
  expandImportedChat?: boolean;
}

export function ConversationView({
  conversation,
  isLoading = false,
  onConversationDeleted,
  onTitleUpdated,
  onConversationLocked,
  expandImportedChat = false,
}: ConversationViewProps) {
  const [showConversation, setShowConversation] = useState(expandImportedChat);
  const [showProjectDraft, setShowProjectDraft] = useState(true);
  const [mobileProjectView, setMobileProjectView] = useState<"chat" | "draft">("draft");
  const researchRuns =
    ((conversation as unknown as { research_runs?: unknown[] })?.research_runs ?? []) as
      | Array<Record<string, unknown>>
      | [];
  const [activeRunDetails, setActiveRunDetails] = useState<
    Record<string, { stage_progress?: unknown; logs?: unknown; experiment_nodes?: unknown[] }>
  >({});
  const [runDetailsError, setRunDetailsError] = useState<string | null>(null);

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

  useEffect(() => {
    if (!conversation?.id || researchRuns.length === 0) {
      return;
    }
    let isCancelled = false;
    const loadDetails = async (): Promise<void> => {
      try {
        const detailEntries = await Promise.all(
          researchRuns.map(async (run) => {
            const runId = (run?.run_id as string) ?? "";
            if (!runId) {
              return [runId, null] as const;
            }
            try {
              const data = await apiFetch<Record<string, unknown>>(
                `/conversations/${conversation.id}/idea/research-run/${runId}`,
              );
              return [runId, data] as const;
            } catch (error) {
              if (error instanceof Error && "status" in error && error.status === 404) {
                return [
                  runId,
                  {
                    debug: "Run details not yet available (404)",
                  },
                ] as const;
              }
              throw error;
            }
          }),
        );
        if (!isCancelled) {
          const map: Record<string, Record<string, unknown>> = {};
          for (const [runId, data] of detailEntries) {
            if (runId && data) {
              map[runId] = data;
            }
          }
          setActiveRunDetails(map);
          setRunDetailsError(null);
        }
      } catch (error) {
        if (!isCancelled) {
          setRunDetailsError(
            error instanceof Error ? error.message : "Unable to load run details",
          );
        }
      }
    };
    void loadDetails();
    return () => {
      isCancelled = true;
    };
  }, [conversation?.id, researchRuns]);

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
            Welcome to AGI Judd&apos;s Idea Catalog
          </h2>
          <p className="text-muted-foreground mb-4">
            Transform imported conversations into Data Science experiments
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
      <div className="h-[calc(100vh-180px)] flex flex-col overflow-hidden">
        {researchRuns.length > 0 && (
          <div className="bg-muted text-muted-foreground text-xs p-3 rounded-md mb-3 max-h-48 overflow-auto">
            <p className="font-medium text-foreground mb-2">Research Pipeline Runs (debug view)</p>
            <pre className="whitespace-pre-wrap text-foreground">
              {JSON.stringify(researchRuns, null, 2)}
            </pre>
            {runDetailsError && (
              <p className="text-destructive mt-2">Detail fetch error: {runDetailsError}</p>
            )}
            {Object.keys(activeRunDetails).length > 0 && (
              <>
                <p className="font-medium text-foreground mt-3 mb-2">
                  Research Run Details (debug view)
                </p>
                <pre className="whitespace-pre-wrap text-foreground">
                  {JSON.stringify(activeRunDetails, null, 2)}
                </pre>
              </>
            )}
          </div>
        )}
        <ConversationHeader
          conversation={conversation}
          onConversationDeleted={onConversationDeleted}
          onTitleUpdated={onTitleUpdated}
          viewMode={viewMode}
          onViewModeChange={handleViewModeChange}
        />

        {/* Dynamic Content Area - Flexbox layout for smart space allocation */}
        <div className="flex-1 min-h-0 overflow-hidden">
          <ProjectDraftTab
            conversation={conversation}
            mobileView={mobileProjectView}
            onMobileViewChange={setMobileProjectView}
            onConversationLocked={onConversationLocked}
          />
        </div>
      </div>
    </ConversationProvider>
  );
}
