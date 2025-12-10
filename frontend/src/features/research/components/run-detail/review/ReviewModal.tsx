"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { createPortal } from "react-dom";
import { Loader2, AlertCircle } from "lucide-react";
import type { LlmReviewResponse } from "@/types/research";
import { ReviewHeader } from "./ReviewHeader";
import { ReviewTabs } from "./ReviewTabs";
import { ReviewScores } from "./ReviewScores";
import { ReviewAnalysis } from "./ReviewAnalysis";

interface ReviewModalProps {
  review: LlmReviewResponse | null;
  notFound: boolean;
  error: string | null;
  onClose: () => void;
  loading?: boolean;
}

/**
 * ReviewModal Component
 *
 * Main modal dialog for displaying LLM review data.
 * Features:
 * - Portal rendering to avoid layout stacking context issues
 * - Fixed overlay with semi-transparent background
 * - Tab navigation: "Both", "Scores", "Analysis"
 * - Conditional content rendering based on active tab
 * - Loading, error, and not-found states
 * - ESC key to close
 * - SSR-safe with isClient check
 *
 * Layout:
 * - Header with title and verdict badge
 * - Tab navigation
 * - Content area with conditional rendering
 *
 * @param review - The LlmReviewResponse object (null while loading)
 * @param notFound - Whether the review was not found for this run
 * @param error - Error message if review loading failed
 * @param onClose - Callback when user closes the modal
 * @param loading - Whether data is currently being loaded
 */
export function ReviewModal({
  review,
  notFound,
  error,
  onClose,
  loading = false,
}: ReviewModalProps) {
  const [isClient, setIsClient] = useState(false);
  const [activeTab, setActiveTab] = useState<"both" | "scores" | "analysis">("both");
  const modalRef = useRef<HTMLDivElement>(null);
  const previousActiveElement = useRef<Element | null>(null);

  useEffect(() => {
    setIsClient(true);
    // Store the previously focused element to restore on close
    previousActiveElement.current = document.activeElement;
  }, []);

  // Focus trap and keyboard handling
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
        return;
      }

      // Focus trap - Tab and Shift+Tab
      if (e.key === "Tab" && modalRef.current) {
        const focusableElements = modalRef.current.querySelectorAll<HTMLElement>(
          'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
        );
        const firstElement = focusableElements[0];
        const lastElement = focusableElements[focusableElements.length - 1];

        if (e.shiftKey && document.activeElement === firstElement) {
          e.preventDefault();
          lastElement?.focus();
        } else if (!e.shiftKey && document.activeElement === lastElement) {
          e.preventDefault();
          firstElement?.focus();
        }
      }
    },
    [onClose]
  );

  useEffect(() => {
    if (!isClient) return;

    document.addEventListener("keydown", handleKeyDown);
    // Focus the modal when it opensN
    modalRef.current?.focus();
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      // Restore focus when modal closes
      if (previousActiveElement.current instanceof HTMLElement) {
        previousActiveElement.current.focus();
      }
    };
  }, [isClient, handleKeyDown]);

  if (!isClient) return null;

  const showLoading = loading && !review;
  const showError = error && !review && !loading;
  const showNotFound = notFound && !review && !loading;
  const showContent = review && !loading;

  return createPortal(
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black bg-opacity-50"
      role="dialog"
      aria-modal="true"
      aria-labelledby="modal-title"
    >
      <div
        ref={modalRef}
        tabIndex={-1}
        className="relative bg-card rounded-lg p-4 sm:p-6 w-full sm:max-w-4xl max-h-[90vh] overflow-y-auto focus:outline-none"
      >
        {showLoading && (
          <div className="flex items-center justify-center h-64">
            <Loader2 className="h-8 w-8 animate-spin text-primary mr-3" />
            <span className="text-muted-foreground">Loading evaluation...</span>
          </div>
        )}

        {showError && (
          <div className="flex flex-col items-center justify-center gap-4 h-64">
            <AlertCircle className="h-12 w-12 text-red-400" />
            <p className="text-center text-foreground">{error}</p>
            <button onClick={onClose} className="text-sm text-primary hover:text-primary-hover">
              Close
            </button>
          </div>
        )}

        {showNotFound && (
          <div className="flex flex-col items-center justify-center gap-4 h-64">
            <AlertCircle className="h-12 w-12 text-amber-400" />
            <p className="text-center text-foreground">No evaluation available for this run</p>
            <button onClick={onClose} className="text-sm text-primary hover:text-primary-hover">
              Close
            </button>
          </div>
        )}

        {showContent && (
          <>
            <ReviewHeader decision={review.decision} onClose={onClose} />

            <ReviewTabs activeTab={activeTab} onTabChange={setActiveTab} />

            <div className="space-y-6">
              {(activeTab === "both" || activeTab === "scores") && <ReviewScores review={review} />}

              {(activeTab === "both" || activeTab === "analysis") && (
                <ReviewAnalysis review={review} />
              )}
            </div>
          </>
        )}
      </div>
    </div>,
    document.body
  );
}
