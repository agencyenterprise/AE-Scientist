"use client";

import React, { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { AlertTriangle, Loader2 } from "lucide-react";

interface DeleteConfirmModalProps {
  isOpen: boolean;
  title: string;
  isDeleting: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

export function DeleteConfirmModal({
  isOpen,
  title,
  isDeleting,
  onConfirm,
  onCancel,
}: DeleteConfirmModalProps) {
  const [isClient, setIsClient] = useState(false);

  useEffect(() => {
    setIsClient(true);
  }, []);

  if (!isOpen || !isClient) return null;

  return createPortal(
    <div className="fixed inset-0 z-[1000] flex items-center justify-center p-4 bg-black/50">
      <div className="bg-card rounded-lg shadow-xl max-w-md w-full">
        <div className="p-6">
          <div className="flex items-center mb-4">
            <AlertTriangle className="w-6 h-6 text-destructive mr-3" />
            <h3 className="text-lg font-medium text-foreground">Delete Conversation</h3>
          </div>
          <p className="text-sm text-muted-foreground mb-6">
            Are you sure you want to delete &quot;{title}&quot;? This action cannot be undone.
          </p>
          <div className="flex space-x-3 justify-end">
            <button
              onClick={onCancel}
              disabled={isDeleting}
              className="px-4 py-2 text-sm font-medium text-foreground bg-card border border-border rounded-md hover:bg-muted disabled:opacity-50"
            >
              Cancel
            </button>
            <button onClick={onConfirm} disabled={isDeleting} className="btn-danger">
              {isDeleting ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin mr-2" />
                  Deleting...
                </>
              ) : (
                "Delete"
              )}
            </button>
          </div>
        </div>
      </div>
    </div>,
    document.body
  );
}
