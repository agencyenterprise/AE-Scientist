"use client";

import React from "react";
import { Check, X, Pencil, Trash2, Loader2 } from "lucide-react";

interface TitleEditorProps {
  title: string;
  isEditing: boolean;
  editValue: string;
  isUpdating: boolean;
  isDeleting: boolean;
  onEditValueChange: (value: string) => void;
  onStartEdit: () => void;
  onSave: () => void;
  onCancel: () => void;
  onDelete: () => void;
}

export function TitleEditor({
  title,
  isEditing,
  editValue,
  isUpdating,
  isDeleting,
  onEditValueChange,
  onStartEdit,
  onSave,
  onCancel,
  onDelete,
}: TitleEditorProps) {
  const handleKeyDown = (event: React.KeyboardEvent): void => {
    if (event.key === "Enter") {
      onSave();
    } else if (event.key === "Escape") {
      onCancel();
    }
  };

  if (isEditing) {
    return (
      <div className="flex items-center space-x-2">
        <input
          type="text"
          value={editValue}
          onChange={e => onEditValueChange(e.target.value)}
          onKeyDown={handleKeyDown}
          className="text-xl font-bold text-foreground bg-card border border-border rounded px-2 py-1 flex-1 min-w-0 focus:outline-none focus:ring-2 focus:ring-ring shadow-sm"
          disabled={isUpdating}
          autoFocus
        />
        <button
          onClick={onSave}
          disabled={isUpdating || !editValue.trim()}
          className="p-1 text-green-500 hover:opacity-80 disabled:opacity-50 flex-shrink-0"
          title="Save title"
        >
          {isUpdating ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Check className="w-4 h-4" />
          )}
        </button>
        <button
          onClick={onCancel}
          disabled={isUpdating}
          className="p-1 text-muted-foreground hover:text-foreground disabled:opacity-50 flex-shrink-0"
          title="Cancel editing"
        >
          <X className="w-4 h-4" />
        </button>
        <button
          onClick={onDelete}
          disabled={isDeleting}
          className="p-1 text-red-500 hover:text-red-700 transition-colors flex-shrink-0 disabled:opacity-50"
          title="Delete conversation"
        >
          <Trash2 className="w-4 h-4" />
        </button>
      </div>
    );
  }

  return (
    <div className="flex items-center space-x-2">
      <h1 className="text-xl font-bold text-foreground truncate">{title}</h1>
      <button
        onClick={onStartEdit}
        className="p-1 text-muted-foreground hover:text-foreground transition-colors flex-shrink-0"
        title="Edit title"
      >
        <Pencil className="w-4 h-4" />
      </button>
      <button
        onClick={onDelete}
        disabled={isDeleting}
        className="p-1 text-red-500 hover:text-red-700 transition-colors flex-shrink-0 disabled:opacity-50"
        title="Delete conversation"
      >
        <Trash2 className="w-4 h-4" />
      </button>
    </div>
  );
}
