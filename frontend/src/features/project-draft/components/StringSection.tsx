import { ReactElement } from "react";
import ReactMarkdown from "react-markdown";
import { Pencil } from "lucide-react";

import { cn } from "@/shared/lib/utils";
import { markdownComponents } from "../utils/markdownComponents";

/**
 * Visual variants for the StringSection component.
 *
 * - `default`: No border, slightly muted text color
 * - `primary-border`: Left border with primary color, full text color (for Hypothesis)
 * - `success-box`: Green background box (for Expected Outcome)
 */
export type StringSectionVariant = "default" | "primary-border" | "success-box";

/**
 * Props for the StringSection component.
 */
export interface StringSectionProps {
  /** Section title (displayed as uppercase label) */
  title: string;
  /** Section content (rendered as Markdown) */
  content: string;
  /** Diff content for comparison mode (overrides content) */
  diffContent?: ReactElement[] | null;
  /** Edit button click handler */
  onEdit?: () => void;
  /** Visual variant */
  variant?: StringSectionVariant;
  /** Additional CSS classes */
  className?: string;
}

/**
 * Reusable section component for displaying string content.
 *
 * This component consolidates the common pattern used by HypothesisSection,
 * AbstractSection, RelatedWorkSection, and ExpectedOutcomeSection.
 *
 * Features:
 * - Markdown rendering with custom components
 * - Optional diff content display
 * - Optional edit button
 * - Multiple visual variants for different section types
 *
 * @example
 * ```tsx
 * // Hypothesis section with primary border
 * <StringSection
 *   title="Hypothesis"
 *   content={hypothesis}
 *   variant="primary-border"
 *   onEdit={() => handleEditSection('hypothesis')}
 * />
 *
 * // Abstract section with default styling
 * <StringSection
 *   title="Abstract"
 *   content={abstract}
 *   onEdit={() => handleEditSection('abstract')}
 * />
 *
 * // Expected outcome with success box styling
 * <StringSection
 *   title="Expected Outcome"
 *   content={expectedOutcome}
 *   variant="success-box"
 *   onEdit={() => handleEditSection('expected_outcome')}
 * />
 *
 * // With diff content
 * <StringSection
 *   title="Abstract"
 *   content={abstract}
 *   diffContent={abstractDiff}
 * />
 * ```
 */
export function StringSection({
  title,
  content,
  diffContent,
  onEdit,
  variant = "default",
  className,
}: StringSectionProps) {
  // Container styles based on variant
  const containerStyles = cn(
    // Base styles
    "",
    // Variant-specific styles
    {
      "": variant === "default",
      "border-l-4 border-primary pl-4": variant === "primary-border",
    },
    className
  );

  // Content wrapper styles based on variant
  const contentWrapperStyles = cn(
    // Base styles
    "text-sm leading-relaxed",
    // Variant-specific styles
    {
      "text-foreground/90": variant === "default",
      "text-foreground": variant === "primary-border",
      "text-foreground bg-green-500/10 border border-green-500/30 rounded-xl p-4":
        variant === "success-box",
    }
  );

  // Margin between title and content
  const marginStyles = variant === "primary-border" ? "mb-1" : "mb-2";

  return (
    <div className={containerStyles}>
      <div className={cn("flex items-center justify-between", marginStyles)}>
        <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
          {title}
        </h3>
        {onEdit && (
          <button
            onClick={onEdit}
            className="p-1 text-muted-foreground hover:text-foreground hover:bg-muted rounded transition-colors"
            aria-label={`Edit ${title.toLowerCase()}`}
          >
            <Pencil className="w-3.5 h-3.5" />
          </button>
        )}
      </div>
      <div className={contentWrapperStyles}>
        {diffContent ? (
          <div className="whitespace-pre-wrap">{diffContent}</div>
        ) : (
          <ReactMarkdown components={markdownComponents}>{content}</ReactMarkdown>
        )}
      </div>
    </div>
  );
}
