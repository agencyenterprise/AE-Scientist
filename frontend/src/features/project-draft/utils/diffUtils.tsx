import type { ReactElement } from "react";
import { diff_match_patch } from "diff-match-patch";
import type { IdeaVersion } from "@/types";

/**
 * Interface for diff result with React elements
 */
export interface DiffContent {
  elements: ReactElement[];
}

/**
 * Interface for all section diffs
 */
export interface SectionDiffs {
  title: ReactElement[] | null;
  hypothesis: ReactElement[] | null;
  relatedWork: ReactElement[] | null;
  abstract: ReactElement[] | null;
  expectedOutcome: ReactElement[] | null;
  experiments: (ReactElement[] | null)[];
  riskFactors: (ReactElement[] | null)[];
  // Track deleted items (items in old version but not in new)
  deletedExperiments: ReactElement[][];
  deletedRiskFactors: ReactElement[][];
}

/**
 * Generate diff elements for a string comparison
 */
export function generateStringDiff(
  oldText: string,
  newText: string,
  keyPrefix: string = "diff"
): ReactElement[] {
  if (oldText === newText) {
    return [
      <span key={`${keyPrefix}-0`} className="text-foreground">
        {newText}
      </span>,
    ];
  }

  const dmp = new diff_match_patch();
  const diffs = dmp.diff_main(oldText, newText);
  dmp.diff_cleanupSemantic(diffs);

  return diffs.map((diff, index) => {
    const [operation, text] = diff;

    if (operation === 0) {
      // No change
      return (
        <span key={`${keyPrefix}-${index}`} className="text-foreground">
          {text}
        </span>
      );
    } else if (operation === -1) {
      // Deletion
      return (
        <span key={`${keyPrefix}-${index}`} className="bg-red-500/20 text-red-400 px-0.5 rounded">
          <span className="line-through">{text}</span>
        </span>
      );
    } else {
      // Addition
      return (
        <span
          key={`${keyPrefix}-${index}`}
          className="bg-green-500/20 text-green-400 px-0.5 rounded"
        >
          <span className="font-medium">{text}</span>
        </span>
      );
    }
  });
}

/**
 * Generate diff content showing entire text as deleted
 */
export function generateDeletedDiff(text: string, keyPrefix: string = "del"): ReactElement[] {
  return [
    <span key={`${keyPrefix}-0`} className="bg-red-500/20 text-red-400 px-0.5 rounded">
      <span className="line-through">{text}</span>
    </span>,
  ];
}

/**
 * Generate diff content showing entire text as added
 */
export function generateAddedDiff(text: string, keyPrefix: string = "add"): ReactElement[] {
  return [
    <span key={`${keyPrefix}-0`} className="bg-green-500/20 text-green-400 px-0.5 rounded">
      <span className="font-medium">{text}</span>
    </span>,
  ];
}

/**
 * Generate diff content for title comparison between two versions
 */
export function generateTitleDiff(
  fromVersion: IdeaVersion,
  toVersion: IdeaVersion
): ReactElement[] {
  return generateStringDiff(fromVersion.title, toVersion.title, "title");
}

/**
 * Generate diff content for all sections between two versions
 */
export function generateSectionDiffs(
  fromVersion: IdeaVersion,
  toVersion: IdeaVersion
): SectionDiffs {
  // String section diffs
  const title = generateStringDiff(fromVersion.title, toVersion.title, "title");

  const hypothesis = generateStringDiff(
    fromVersion.short_hypothesis || "",
    toVersion.short_hypothesis || "",
    "hypothesis"
  );

  const relatedWork = generateStringDiff(
    fromVersion.related_work || "",
    toVersion.related_work || "",
    "related-work"
  );

  const abstract = generateStringDiff(
    fromVersion.abstract || "",
    toVersion.abstract || "",
    "abstract"
  );

  const expectedOutcome = generateStringDiff(
    fromVersion.expected_outcome || "",
    toVersion.expected_outcome || "",
    "expected-outcome"
  );

  // Array section diffs - experiments
  const oldExperiments = fromVersion.experiments || [];
  const newExperiments = toVersion.experiments || [];
  const maxExpLen = Math.max(oldExperiments.length, newExperiments.length);

  const experiments: (ReactElement[] | null)[] = [];
  const deletedExperiments: ReactElement[][] = [];

  for (let i = 0; i < maxExpLen; i++) {
    const oldExp = oldExperiments[i];
    const newExp = newExperiments[i];

    if (oldExp && newExp) {
      // Both exist - show diff
      experiments.push(generateStringDiff(oldExp, newExp, `exp-${i}`));
    } else if (newExp && !oldExp) {
      // New item added
      experiments.push(generateAddedDiff(newExp, `exp-add-${i}`));
    } else if (oldExp && !newExp) {
      // Item deleted - track separately
      deletedExperiments.push(generateDeletedDiff(oldExp, `exp-del-${i}`));
    }
  }

  // Array section diffs - risk factors
  const oldRisks = fromVersion.risk_factors_and_limitations || [];
  const newRisks = toVersion.risk_factors_and_limitations || [];
  const maxRiskLen = Math.max(oldRisks.length, newRisks.length);

  const riskFactors: (ReactElement[] | null)[] = [];
  const deletedRiskFactors: ReactElement[][] = [];

  for (let i = 0; i < maxRiskLen; i++) {
    const oldRisk = oldRisks[i];
    const newRisk = newRisks[i];

    if (oldRisk && newRisk) {
      // Both exist - show diff
      riskFactors.push(generateStringDiff(oldRisk, newRisk, `risk-${i}`));
    } else if (newRisk && !oldRisk) {
      // New item added
      riskFactors.push(generateAddedDiff(newRisk, `risk-add-${i}`));
    } else if (oldRisk && !newRisk) {
      // Item deleted - track separately
      deletedRiskFactors.push(generateDeletedDiff(oldRisk, `risk-del-${i}`));
    }
  }

  return {
    title,
    hypothesis,
    relatedWork,
    abstract,
    expectedOutcome,
    experiments,
    riskFactors,
    deletedExperiments,
    deletedRiskFactors,
  };
}

/**
 * Check if two versions can be compared for diffs
 */
export function canCompareVersions(
  fromVersion: IdeaVersion | null,
  toVersion: IdeaVersion | null
): boolean {
  return !!(fromVersion && toVersion && fromVersion.version_id !== toVersion.version_id);
}
