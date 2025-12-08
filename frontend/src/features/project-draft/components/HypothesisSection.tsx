import { ReactElement } from "react";
import { StringSection } from "./StringSection";

interface HypothesisSectionProps {
  content: string;
  diffContent?: ReactElement[] | null;
  onEdit?: () => void;
}

/**
 * Section component for displaying the research hypothesis.
 *
 * Uses the primary-border variant for visual emphasis.
 */
export function HypothesisSection({ content, diffContent, onEdit }: HypothesisSectionProps) {
  return (
    <StringSection
      title="Research Hypothesis"
      content={content}
      diffContent={diffContent}
      onEdit={onEdit}
      variant="primary-border"
    />
  );
}
