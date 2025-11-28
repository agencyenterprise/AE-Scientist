"use client";

import { useState, useEffect } from "react";
import { createPortal } from "react-dom";
import { X, Plus, Trash2, ChevronUp, ChevronDown } from "lucide-react";

interface ArraySectionEditModalProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  items: string[];
  onSave: (newItems: string[]) => Promise<void>;
  onSaveNewItem?: (value: string) => Promise<void>;
  editingIndex?: number | null; // If provided, edit only this item
  isAddingNew?: boolean; // If true, adding a new item
  itemLabel?: string; // e.g., "Experiment", "Risk Factor"
  isSaving?: boolean;
}

export function ArraySectionEditModal({
  isOpen,
  onClose,
  title,
  items,
  onSave,
  onSaveNewItem,
  editingIndex = null,
  isAddingNew = false,
  itemLabel = "Item",
  isSaving = false,
}: ArraySectionEditModalProps): React.JSX.Element | null {
  const [editItems, setEditItems] = useState<string[]>(items);
  const [singleItemContent, setSingleItemContent] = useState<string>("");
  const [error, setError] = useState<string>("");
  const [isClient, setIsClient] = useState<boolean>(false);

  const isSingleItemMode = editingIndex !== null || isAddingNew;

  useEffect(() => {
    setIsClient(true);
  }, []);

  // Reset content when modal opens
  useEffect(() => {
    if (isOpen) {
      setEditItems([...items]);
      if (isAddingNew) {
        // Adding a new item - start with empty content
        setSingleItemContent("");
      } else if (editingIndex !== null && items[editingIndex]) {
        // Editing existing item
        setSingleItemContent(items[editingIndex]);
      } else {
        setSingleItemContent("");
      }
      setError("");
    }
  }, [isOpen, items, editingIndex, isAddingNew]);

  const handleSave = async (): Promise<void> => {
    setError("");

    try {
      if (isAddingNew && onSaveNewItem) {
        // Adding a new item - validate and save
        if (!singleItemContent.trim()) {
          setError(`${itemLabel} cannot be empty`);
          return;
        }
        await onSaveNewItem(singleItemContent.trim());
      } else if (isSingleItemMode && editingIndex !== null) {
        // Save single existing item
        if (!singleItemContent.trim()) {
          setError(`${itemLabel} cannot be empty`);
          return;
        }
        const newItems = [...items];
        newItems[editingIndex] = singleItemContent.trim();
        await onSave(newItems);
        onClose();
      } else {
        // Save all items - filter out empty items
        const nonEmptyItems = editItems.map(item => item.trim()).filter(item => item);
        if (nonEmptyItems.length === 0) {
          setError(`At least one ${itemLabel.toLowerCase()} is required`);
          return;
        }
        await onSave(nonEmptyItems);
        onClose();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save");
    }
  };

  const handleAddItem = (): void => {
    setEditItems([...editItems, ""]);
  };

  const handleRemoveItem = (index: number): void => {
    const newItems = editItems.filter((_, i) => i !== index);
    setEditItems(newItems);
  };

  const handleUpdateItem = (index: number, value: string): void => {
    const newItems = [...editItems];
    newItems[index] = value;
    setEditItems(newItems);
  };

  const handleMoveItem = (index: number, direction: "up" | "down"): void => {
    const newIndex = direction === "up" ? index - 1 : index + 1;
    if (newIndex < 0 || newIndex >= editItems.length) return;

    const newItems = [...editItems];
    const temp = newItems[index];
    newItems[index] = newItems[newIndex] as string;
    newItems[newIndex] = temp as string;
    setEditItems(newItems);
  };

  const handleKeyDown = (event: React.KeyboardEvent): void => {
    if (event.key === "Escape") {
      onClose();
    } else if (event.key === "Enter" && event.ctrlKey) {
      handleSave();
    }
  };

  const handleClose = (): void => {
    setError("");
    setEditItems([]);
    setSingleItemContent("");
    onClose();
  };

  if (!isOpen || !isClient) return null;

  return createPortal(
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black bg-opacity-50">
      <div className="relative bg-card rounded-lg p-4 sm:p-6 w-full sm:max-w-3xl max-h-[90vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-semibold text-foreground">
            {isAddingNew
              ? `Add New ${itemLabel}`
              : isSingleItemMode
                ? `Edit ${itemLabel} ${(editingIndex ?? 0) + 1}`
                : `Edit ${title}`}
          </h2>
          <button
            onClick={handleClose}
            className="text-muted-foreground hover:text-foreground p-1 rounded-md hover:bg-muted transition-colors"
            disabled={isSaving}
            aria-label="Close modal"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Error message */}
        {error && (
          <div className="mb-4 p-3 bg-destructive/10 border border-destructive/30 text-destructive rounded text-sm">
            {error}
          </div>
        )}

        {/* Content */}
        <div className="flex-1 overflow-y-auto min-h-0">
          {isSingleItemMode ? (
            // Single item editing mode
            <div className="flex flex-col h-full">
              <label
                htmlFor="single-item-editor"
                className="block text-sm font-medium text-muted-foreground mb-2"
              >
                {itemLabel} Content (Markdown supported)
              </label>
              <textarea
                id="single-item-editor"
                value={singleItemContent}
                onChange={e => setSingleItemContent(e.target.value)}
                onKeyDown={handleKeyDown}
                className="flex-1 min-h-[300px] sm:min-h-[40vh] w-full p-3 border border-border rounded-md resize-y focus:ring-2 focus:ring-ring focus:border-ring bg-surface text-foreground font-mono text-sm"
                placeholder={`Enter ${itemLabel.toLowerCase()} content...`}
                disabled={isSaving}
                autoFocus
              />
            </div>
          ) : (
            // All items editing mode
            <div className="space-y-3">
              {editItems.map((item, index) => (
                <div
                  key={index}
                  className="flex gap-2 items-start p-3 bg-muted/30 rounded-lg border border-border"
                >
                  {/* Item number */}
                  <div className="flex-shrink-0 w-6 h-6 rounded-full bg-primary/10 text-primary text-xs font-medium flex items-center justify-center mt-1">
                    {index + 1}
                  </div>

                  {/* Textarea */}
                  <textarea
                    value={item}
                    onChange={e => handleUpdateItem(index, e.target.value)}
                    onKeyDown={handleKeyDown}
                    className="flex-1 min-h-[80px] p-2 border border-border rounded-md resize-y focus:ring-2 focus:ring-ring focus:border-ring bg-surface text-foreground text-sm"
                    placeholder={`Enter ${itemLabel.toLowerCase()}...`}
                    disabled={isSaving}
                  />

                  {/* Actions */}
                  <div className="flex flex-col gap-1 flex-shrink-0">
                    <button
                      onClick={() => handleMoveItem(index, "up")}
                      disabled={isSaving || index === 0}
                      className="p-1 text-muted-foreground hover:text-foreground hover:bg-muted rounded disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                      aria-label="Move up"
                    >
                      <ChevronUp className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => handleMoveItem(index, "down")}
                      disabled={isSaving || index === editItems.length - 1}
                      className="p-1 text-muted-foreground hover:text-foreground hover:bg-muted rounded disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                      aria-label="Move down"
                    >
                      <ChevronDown className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => handleRemoveItem(index)}
                      disabled={isSaving || editItems.length <= 1}
                      className="p-1 text-muted-foreground hover:text-destructive hover:bg-destructive/10 rounded disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                      aria-label="Remove item"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              ))}

              {/* Add item button */}
              <button
                onClick={handleAddItem}
                disabled={isSaving}
                className="w-full p-3 border-2 border-dashed border-border rounded-lg text-muted-foreground hover:text-foreground hover:border-primary/50 hover:bg-primary/5 transition-colors flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <Plus className="w-4 h-4" />
                Add {itemLabel}
              </button>
            </div>
          )}

          <p className="mt-3 text-xs text-muted-foreground">
            Press Ctrl+Enter to save, Escape to cancel
          </p>
        </div>

        {/* Footer */}
        <div className="flex justify-end gap-3 mt-6 pt-4 border-t border-border">
          <button
            onClick={handleClose}
            disabled={isSaving}
            className="px-4 py-2 text-sm font-medium text-foreground bg-muted hover:bg-muted/80 rounded-md disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={isSaving}
            className="px-4 py-2 text-sm font-medium text-primary-foreground bg-primary hover:bg-primary-hover rounded-md disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {isSaving ? "Saving..." : "Save"}
          </button>
        </div>
      </div>
    </div>,
    document.body
  );
}
