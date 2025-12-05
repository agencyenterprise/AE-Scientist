import { ReactElement } from "react";
import { StringSection } from "./StringSection";

interface AbstractSectionProps {
  content: string;
  diffContent?: ReactElement[] | null;
  onEdit?: () => void;
}

/**
 * Section component for displaying the abstract.
 *
 * Uses the default variant styling.
 */
export function AbstractSection({ content, diffContent, onEdit }: AbstractSectionProps) {
  return (
    <StringSection title="Abstract" content={content} diffContent={diffContent} onEdit={onEdit} />
  );
}
