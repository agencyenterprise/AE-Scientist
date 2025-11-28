"use client";

import { useCallback, useState } from "react";

export interface UsePromptModalReturn {
  isOpen: boolean;
  open: () => void;
  close: () => void;
}

/**
 * Simple hook for managing PromptEditModal open/close state.
 * Reusable across any component that needs to show the prompt modal.
 */
export function usePromptModal(): UsePromptModalReturn {
  const [isOpen, setIsOpen] = useState(false);

  const open = useCallback(() => setIsOpen(true), []);
  const close = useCallback(() => setIsOpen(false), []);

  return { isOpen, open, close };
}
