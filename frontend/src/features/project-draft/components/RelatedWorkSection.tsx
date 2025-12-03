import { ReactElement } from "react";
import { StringSection } from "./StringSection";

interface RelatedWorkSectionProps {
  content: string;
  diffContent?: ReactElement[] | null;
  onEdit?: () => void;
}

/**
 * Section component for displaying related work.
 *
 * Uses the default variant styling.
 */
export function RelatedWorkSection({ content, diffContent, onEdit }: RelatedWorkSectionProps) {
  return (
    <StringSection
      title="Related Work"
      content={content}
      diffContent={diffContent}
      onEdit={onEdit}
    />
  );
}
