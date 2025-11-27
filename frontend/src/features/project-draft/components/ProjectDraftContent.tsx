import React from "react";

import type { Idea } from "@/types";

import { isIdeaGenerating } from "../utils/versionUtils";
import { ProjectDraftEditForm } from "./ProjectDraftEditForm";
import { ProjectDraftSkeleton } from "./ProjectDraftSkeleton";
import { HypothesisSection } from "./HypothesisSection";
import { RelatedWorkSection } from "./RelatedWorkSection";
import { AbstractSection } from "./AbstractSection";
import { ExperimentsSection } from "./ExperimentsSection";
import { ExpectedOutcomeSection } from "./ExpectedOutcomeSection";
import { RiskFactorsSection } from "./RiskFactorsSection";

interface ProjectDraftContentProps {
  projectDraft: Idea;
  isEditing: boolean;
  editDescription: string;
  setEditDescription: (description: string) => void;
  onKeyDown: (event: React.KeyboardEvent, action: () => void) => void;
  onSave: () => Promise<void>;
  onCancelEdit: () => void;
}

export function ProjectDraftContent({
  projectDraft,
  isEditing,
  editDescription,
  setEditDescription,
  onKeyDown,
  onSave,
  onCancelEdit,
}: ProjectDraftContentProps): React.JSX.Element {
  const isGenerating = isIdeaGenerating(projectDraft);
  const activeVersion = projectDraft.active_version;

  if (isEditing) {
    return (
      <ProjectDraftEditForm
        editDescription={editDescription}
        setEditDescription={setEditDescription}
        onKeyDown={onKeyDown}
        onSave={onSave}
        onCancelEdit={onCancelEdit}
      />
    );
  }

  return (
    <div className="flex-1 flex flex-col min-h-0 overflow-hidden">
      <div className="flex-1 overflow-y-auto px-1 space-y-6">
        {isGenerating ? (
          <ProjectDraftSkeleton />
        ) : (
          <>
            {activeVersion?.short_hypothesis && (
              <HypothesisSection content={activeVersion.short_hypothesis} />
            )}

            {activeVersion?.related_work && (
              <RelatedWorkSection content={activeVersion.related_work} />
            )}

            {activeVersion?.abstract && <AbstractSection content={activeVersion.abstract} />}

            {activeVersion?.experiments && activeVersion.experiments.length > 0 && (
              <ExperimentsSection experiments={activeVersion.experiments} />
            )}

            {activeVersion?.expected_outcome && (
              <ExpectedOutcomeSection content={activeVersion.expected_outcome} />
            )}

            {activeVersion?.risk_factors_and_limitations &&
              activeVersion.risk_factors_and_limitations.length > 0 && (
                <RiskFactorsSection risks={activeVersion.risk_factors_and_limitations} />
              )}
          </>
        )}
      </div>
    </div>
  );
}
