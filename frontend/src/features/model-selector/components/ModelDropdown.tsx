"use client";

import { ModelOption } from "@/features/model-selector/components/ModelOption";
import type { DropdownCoords } from "@/features/model-selector/hooks/useDropdownPosition";
import {
  type ConversationCapabilities,
  getIncompatibilityReason,
  isModelCompatible,
  isModelDefault,
} from "@/features/model-selector/utils/modelUtils";
import type { LLMDefault, LLMModel } from "@/types";
import { RefObject, useState } from "react";
import { createPortal } from "react-dom";
import { X } from "lucide-react";

interface ModelDropdownProps {
  providers: Record<string, LLMModel[]>;
  currentProvider: string;
  currentModel: string;
  defaultModel: LLMDefault | null;
  conversationCapabilities?: ConversationCapabilities;
  showCapabilities: boolean;
  showMakeDefault: boolean;
  isUpdatingDefault: boolean;
  isCurrentSelectionDefault: boolean;
  isUsingCustomSelection: boolean;
  coords: DropdownCoords;
  position: "left" | "right";
  verticalPosition: "above" | "below";
  searchInputRef: RefObject<HTMLInputElement | null>;
  selectedModelRef: RefObject<HTMLButtonElement | null>;
  onSelect: (provider: string, model: string) => void;
  onMakeDefault: () => void;
  onClose: () => void;
}

export function ModelDropdown({
  providers,
  currentProvider,
  currentModel,
  defaultModel,
  conversationCapabilities,
  showCapabilities,
  showMakeDefault,
  isUpdatingDefault,
  isCurrentSelectionDefault,
  isUsingCustomSelection,
  coords,
  position,
  verticalPosition,
  searchInputRef,
  selectedModelRef,
  onSelect,
  onMakeDefault,
  onClose,
}: ModelDropdownProps) {
  const [filterText, setFilterText] = useState("");

  const filteredProviders = filterText.trim()
    ? Object.entries(providers).reduce(
        (acc, [provider, models]) => {
          const searchText = filterText.toLowerCase().trim();
          const providerMatches = provider.toLowerCase().includes(searchText);
          const matchingModels = models.filter(
            model =>
              model.label.toLowerCase().includes(searchText) ||
              model.id.toLowerCase().includes(searchText)
          );

          if (providerMatches || matchingModels.length > 0) {
            acc[provider] = providerMatches ? models : matchingModels;
          }
          return acc;
        },
        {} as Record<string, LLMModel[]>
      )
    : providers;

  const handleClose = () => {
    setFilterText("");
    onClose();
  };

  // Use portal to render at document.body to avoid CSS transform issues
  return createPortal(
    <>
      {/* Backdrop */}
      <div className="fixed inset-0 z-[55]" onClick={handleClose} />

      {/* Dropdown */}
      <div
        className="fixed w-64 bg-card border border-border rounded-md shadow-lg z-[60] flex flex-col"
        style={{
          top: verticalPosition === "below" ? coords.top : "auto",
          bottom: verticalPosition === "above" ? coords.bottom : "auto",
          left: position === "left" ? coords.left : "auto",
          right: position === "right" ? coords.right : "auto",
          maxHeight: coords.maxHeight,
        }}
      >
        {/* Header with close button */}
        <div className="flex items-center justify-between px-3 py-2 border-b border-border bg-muted">
          <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
            Select Model
          </span>
          <button
            type="button"
            onClick={handleClose}
            className="text-muted-foreground hover:text-foreground p-0.5 rounded transition-colors"
            title="Close"
          >
            <X className="w-3 h-3" />
          </button>
        </div>

        {/* Search Input */}
        <div className="p-2 border-b border-border">
          <input
            ref={searchInputRef}
            type="text"
            placeholder="Search models..."
            value={filterText}
            onChange={e => setFilterText(e.target.value)}
            className="w-full px-2 py-1 text-xs border border-border rounded focus:outline-none focus:ring-1 focus:ring-primary focus:border-primary bg-card text-foreground"
            onClick={e => e.stopPropagation()}
            onKeyDown={e => {
              if (e.key === "Enter") {
                e.preventDefault();
              }
            }}
          />
        </div>

        {/* Model list */}
        <div className="flex-1 min-h-0 overflow-y-auto">
          {Object.keys(filteredProviders).length === 0 && filterText.trim() ? (
            <div className="p-4 text-center text-xs text-muted-foreground">
              <div className="mb-1">No models found</div>
              <div>Try adjusting your search</div>
            </div>
          ) : (
            Object.entries(filteredProviders).map(([provider, models]) => (
              <div key={provider} className="border-b border-border last:border-b-0">
                <div className="px-3 py-2 bg-muted text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                  {provider}
                </div>
                {models.map(model => (
                  <ModelOption
                    key={`${provider}-${model.id}`}
                    provider={provider}
                    model={model}
                    isSelected={currentProvider === provider && currentModel === model.id}
                    isDefault={isModelDefault(defaultModel, provider, model.id)}
                    isCompatible={isModelCompatible(
                      providers,
                      provider,
                      model.id,
                      conversationCapabilities
                    )}
                    incompatibilityReason={getIncompatibilityReason(
                      providers,
                      provider,
                      model.id,
                      conversationCapabilities
                    )}
                    showCapabilities={showCapabilities}
                    onSelect={onSelect}
                    selectedRef={selectedModelRef}
                  />
                ))}
              </div>
            ))
          )}
        </div>

        {/* Make Default / Already Default section */}
        {showMakeDefault && (
          <div className="border-t border-border p-2">
            {isCurrentSelectionDefault ? (
              <div className="flex items-center justify-center space-x-1 px-2 py-1.5 text-xs font-medium text-green-400 bg-green-500/10 rounded">
                <span>✓</span>
                <span>Already Default</span>
              </div>
            ) : isUsingCustomSelection ? (
              <button
                type="button"
                onClick={onMakeDefault}
                disabled={isUpdatingDefault}
                className="w-full flex items-center justify-center space-x-1 px-2 py-1.5 text-xs font-medium text-primary hover:text-primary hover:bg-primary/10 rounded transition-colors disabled:opacity-50"
              >
                {isUpdatingDefault ? (
                  <>
                    <div className="animate-spin rounded-full h-3 w-3 border-b-2 border-primary"></div>
                    <span>Updating...</span>
                  </>
                ) : (
                  <>
                    <span>⭐</span>
                    <span>Make selection default</span>
                  </>
                )}
              </button>
            ) : null}
          </div>
        )}
      </div>
    </>,
    document.body
  );
}
