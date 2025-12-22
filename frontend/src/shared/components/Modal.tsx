"use client";

import { useEffect, ReactNode } from "react";
import { createPortal } from "react-dom";
import { X } from "lucide-react";

interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  maxWidth?: string;
  maxHeight?: string;
}

/**
 * Reusable modal dialog component with escape key handling
 */
export function Modal({
  isOpen,
  onClose,
  title,
  children,
  maxWidth = "max-w-2xl",
  maxHeight = "max-h-96",
}: ModalProps) {
  useEffect(() => {
    if (!isOpen) return;

    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
      }
    };

    document.addEventListener("keydown", handleEscape);
    return () => document.removeEventListener("keydown", handleEscape);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return createPortal(
    <div className="fixed inset-0 z-[1000] flex items-center justify-center p-4 bg-black/50">
      <div
        className={`relative rounded-lg border border-slate-700 bg-slate-800 p-6 shadow-xl ${maxWidth} w-full ${maxHeight} overflow-y-auto`}
      >
        <button
          type="button"
          onClick={onClose}
          className="absolute top-4 right-4 p-1 hover:bg-slate-700 rounded transition-colors flex-shrink-0"
          title="Close modal"
        >
          <X className="w-4 h-4 text-slate-400" />
        </button>
        <h2 className="text-lg font-semibold text-slate-100 mb-4 pr-6">{title}</h2>
        {children}
      </div>
    </div>,
    document.body
  );
}
