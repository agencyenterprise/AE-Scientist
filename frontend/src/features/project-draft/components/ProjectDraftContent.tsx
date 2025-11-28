import React from "react";

import type { Idea } from "@/types";
import type { SectionDiffs } from "../utils/diffUtils";

import { isIdeaGenerating } from "../utils/versionUtils";
import {
  useSectionEdit,
  SECTION_TITLES,
  ARRAY_ITEM_LABELS,
  type StringSection,
  type ArraySection,
} from "../hooks/useSectionEdit";
import { ProjectDraftSkeleton } from "./ProjectDraftSkeleton";
import { HypothesisSection } from "./HypothesisSection";
import { RelatedWorkSection } from "./RelatedWorkSection";
import { AbstractSection } from "./AbstractSection";
import { ExperimentsSection } from "./ExperimentsSection";
import { ExpectedOutcomeSection } from "./ExpectedOutcomeSection";
import { RiskFactorsSection } from "./RiskFactorsSection";
import { SectionEditModal } from "./SectionEditModal";
import { ArraySectionEditModal } from "./ArraySectionEditModal";

interface ProjectDraftContentProps {
  projectDraft: Idea;
  conversationId: string;
  onUpdate: (updatedIdea: Idea) => void;
  sectionDiffs?: SectionDiffs | null;
}

export function ProjectDraftContent({
  projectDraft,
  conversationId,
  onUpdate,
  sectionDiffs,
}: ProjectDraftContentProps): React.JSX.Element {
  const isGenerating = isIdeaGenerating(projectDraft);
  const activeVersion = projectDraft.active_version;

  const sectionEdit = useSectionEdit({
    conversationId,
    projectDraft,
    onUpdate,
  });

  // Helper to determine which modal to show
  const isStringSectionActive = (section: StringSection): boolean => {
    return (
      sectionEdit.activeSection === section &&
      sectionEdit.activeItemIndex === null &&
      !sectionEdit.isEditingAllItems
    );
  };

  const isArraySectionActive = (section: ArraySection): boolean => {
    return (
      sectionEdit.activeSection === section &&
      (sectionEdit.activeItemIndex !== null ||
        sectionEdit.isEditingAllItems ||
        sectionEdit.isAddingNewItem)
    );
  };

  // Get the currently active string section for the modal
  const getActiveStringSection = (): StringSection | null => {
    const stringSections: StringSection[] = [
      "hypothesis",
      "related_work",
      "abstract",
      "expected_outcome",
    ];
    for (const section of stringSections) {
      if (isStringSectionActive(section)) {
        return section;
      }
    }
    return null;
  };

  // Get the currently active array section for the modal
  const getActiveArraySection = (): ArraySection | null => {
    const arraySections: ArraySection[] = ["experiments", "risk_factors"];
    for (const section of arraySections) {
      if (isArraySectionActive(section)) {
        return section;
      }
    }
    return null;
  };

  const activeStringSection = getActiveStringSection();
  const activeArraySection = getActiveArraySection();

  return (
    <>
      <div className="flex-1 flex flex-col min-h-0 overflow-hidden">
        <div className="flex-1 overflow-y-auto px-1 space-y-6">
          {isGenerating ? (
            <ProjectDraftSkeleton />
          ) : (
            <>
              {activeVersion?.short_hypothesis && (
                <HypothesisSection
                  content={activeVersion.short_hypothesis}
                  diffContent={sectionDiffs?.hypothesis}
                  onEdit={() => sectionEdit.openSection("hypothesis")}
                />
              )}

              {activeVersion?.related_work && (
                <RelatedWorkSection
                  content={activeVersion.related_work}
                  diffContent={sectionDiffs?.relatedWork}
                  onEdit={() => sectionEdit.openSection("related_work")}
                />
              )}

              {activeVersion?.abstract && (
                <AbstractSection
                  content={activeVersion.abstract}
                  diffContent={sectionDiffs?.abstract}
                  onEdit={() => sectionEdit.openSection("abstract")}
                />
              )}

              {activeVersion?.experiments && activeVersion.experiments.length > 0 && (
                <ExperimentsSection
                  experiments={activeVersion.experiments}
                  diffContent={sectionDiffs?.experiments}
                  deletedItems={sectionDiffs?.deletedExperiments}
                  onEditAll={() => sectionEdit.openArrayAll("experiments")}
                  onEditItem={index => sectionEdit.openArrayItem("experiments", index)}
                  onAddItem={() => sectionEdit.openAddNewItem("experiments")}
                  onDeleteItem={index => sectionEdit.deleteArrayItem("experiments", index)}
                  isDeleting={sectionEdit.isSaving}
                />
              )}

              {activeVersion?.expected_outcome && (
                <ExpectedOutcomeSection
                  content={activeVersion.expected_outcome}
                  diffContent={sectionDiffs?.expectedOutcome}
                  onEdit={() => sectionEdit.openSection("expected_outcome")}
                />
              )}

              {activeVersion?.risk_factors_and_limitations &&
                activeVersion.risk_factors_and_limitations.length > 0 && (
                  <RiskFactorsSection
                    risks={activeVersion.risk_factors_and_limitations}
                    diffContent={sectionDiffs?.riskFactors}
                    deletedItems={sectionDiffs?.deletedRiskFactors}
                    onEditAll={() => sectionEdit.openArrayAll("risk_factors")}
                    onEditItem={index => sectionEdit.openArrayItem("risk_factors", index)}
                    onAddItem={() => sectionEdit.openAddNewItem("risk_factors")}
                    onDeleteItem={index => sectionEdit.deleteArrayItem("risk_factors", index)}
                    isDeleting={sectionEdit.isSaving}
                  />
                )}
            </>
          )}
        </div>
      </div>

      {/* String Section Edit Modal */}
      {activeStringSection && (
        <SectionEditModal
          isOpen={true}
          onClose={sectionEdit.close}
          title={SECTION_TITLES[activeStringSection]}
          content={sectionEdit.getStringContent(activeStringSection)}
          onSave={value => sectionEdit.saveString(activeStringSection, value)}
          isSaving={sectionEdit.isSaving}
        />
      )}

      {/* Array Section Edit Modal */}
      {activeArraySection && (
        <ArraySectionEditModal
          isOpen={true}
          onClose={sectionEdit.close}
          title={SECTION_TITLES[activeArraySection]}
          items={sectionEdit.getArrayContent(activeArraySection)}
          onSave={items => sectionEdit.saveArray(activeArraySection, items)}
          onSaveNewItem={value => sectionEdit.saveNewArrayItem(activeArraySection, value)}
          editingIndex={sectionEdit.activeItemIndex}
          isAddingNew={sectionEdit.isAddingNewItem}
          itemLabel={ARRAY_ITEM_LABELS[activeArraySection]}
          isSaving={sectionEdit.isSaving}
        />
      )}
    </>
  );
}
