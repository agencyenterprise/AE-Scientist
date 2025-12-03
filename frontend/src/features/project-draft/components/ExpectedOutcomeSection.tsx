import { ReactElement } from "react";
import { StringSection } from "./StringSection";

interface ExpectedOutcomeSectionProps {
  content: string;
  diffContent?: ReactElement[] | null;
  onEdit?: () => void;
}

/**
 * Section component for displaying the expected outcome.
 *
 * Uses the success-box variant with green background styling.
 */
export function ExpectedOutcomeSection({
  content,
  diffContent,
  onEdit,
}: ExpectedOutcomeSectionProps) {
  return (
    <StringSection
      title="Expected Outcome"
      content={content}
      diffContent={diffContent}
      onEdit={onEdit}
      variant="success-box"
    />
  );
}
