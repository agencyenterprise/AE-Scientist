"use client";

import { ModelDropdown } from "@/features/model-selector/components/ModelDropdown";
import { useDropdownPosition } from "@/features/model-selector/hooks/useDropdownPosition";
import { useModelSelectorData } from "@/features/model-selector/hooks/useModelSelectorData";
import {
  type ConversationCapabilities,
  findFirstCompatibleModel,
  getModelCapabilities,
  getModelLabel,
  isModelCompatible,
  isModelDefault,
} from "@/features/model-selector/utils/modelUtils";
import { useEffect } from "react";
import { ChevronDown } from "lucide-react";

interface ModelSelectorProps {
  promptType: string;
  onModelChange?: (model: string, provider: string) => void;
  onDefaultsChange?: (model: string, provider: string) => void;
  onCapabilitiesChange?: (capabilities: { supportsImages: boolean; supportsPdfs: boolean }) => void;
  selectedModel?: string;
  selectedProvider?: string;
  disabled?: boolean;
  showMakeDefault?: boolean;
  showCapabilities?: boolean;
  conversationCapabilities?: ConversationCapabilities;
}

export function ModelSelector({
  promptType,
  onModelChange,
  onDefaultsChange,
  onCapabilitiesChange,
  selectedModel,
  selectedProvider,
  disabled = false,
  showMakeDefault = false,
  showCapabilities = true,
  conversationCapabilities,
}: ModelSelectorProps) {
  const { defaultModel, providers, isLoading, updateDefault, isUpdatingDefault } =
    useModelSelectorData({ promptType });

  const {
    buttonRef,
    searchInputRef,
    selectedModelRef,
    isOpen,
    position,
    verticalPosition,
    coords,
    toggle,
    close,
  } = useDropdownPosition();

  // Get current selection (from props or defaults)
  const currentProvider = selectedProvider || defaultModel?.llm_provider || "";
  const currentModel = selectedModel || defaultModel?.llm_model || "";

  // Get the display label for the current model
  const currentModelLabel =
    currentModel && currentProvider
      ? getModelLabel(providers, currentProvider, currentModel)
      : "Default";

  // Check if current selection differs from default
  const isUsingCustomSelection =
    (selectedModel && selectedModel !== defaultModel?.llm_model) ||
    (selectedProvider && selectedProvider !== defaultModel?.llm_provider);

  // Check if current selection is already the default
  const isCurrentSelectionDefault = isModelDefault(defaultModel, currentProvider, currentModel);

  // Notify parent whenever the effective current model changes
  useEffect(() => {
    if (currentModel && currentProvider) {
      onDefaultsChange?.(currentModel, currentProvider);
    }
  }, [currentModel, currentProvider, onDefaultsChange]);

  // Notify parent whenever model capabilities change
  useEffect(() => {
    if (currentModel && currentProvider && Object.keys(providers).length > 0) {
      const capabilities = getModelCapabilities(providers, currentProvider, currentModel);
      onCapabilitiesChange?.(capabilities);
    }
  }, [currentModel, currentProvider, providers, onCapabilitiesChange]);

  // Auto-select compatible model if default is incompatible
  useEffect(() => {
    if (!defaultModel || !conversationCapabilities || Object.keys(providers).length === 0) return;

    const effectiveProvider = selectedProvider || defaultModel.llm_provider;
    const effectiveModel = selectedModel || defaultModel.llm_model;

    if (
      !isModelCompatible(providers, effectiveProvider, effectiveModel, conversationCapabilities)
    ) {
      const compatible = findFirstCompatibleModel(providers, conversationCapabilities);
      if (compatible) {
        onModelChange?.(compatible.model, compatible.provider);
      }
    }
  }, [
    defaultModel,
    conversationCapabilities,
    providers,
    selectedModel,
    selectedProvider,
    onModelChange,
  ]);

  const handleModelSelect = (provider: string, model: string): void => {
    if (!isModelCompatible(providers, provider, model, conversationCapabilities)) {
      return;
    }
    onModelChange?.(model, provider);
  };

  const handleMakeDefault = async (): Promise<void> => {
    if (!currentModel || !currentProvider) return;

    const updatedDefault = await updateDefault(currentProvider, currentModel);
    // Clear any temporary selection since it's now the default
    onModelChange?.("", "");
    // Notify parent about the new current model (which is now the default)
    onDefaultsChange?.(updatedDefault.llm_model, updatedDefault.llm_provider);
    close();
  };

  if (isLoading) {
    return (
      <div className="flex items-center space-x-2 text-xs text-muted-foreground">
        <div className="animate-spin rounded-full h-3 w-3 border-b-2 border-muted-foreground"></div>
        <span>Loading...</span>
      </div>
    );
  }

  return (
    <div className="relative">
      <button
        type="button"
        ref={buttonRef}
        onClick={toggle}
        disabled={disabled}
        className={`flex items-center space-x-1 px-2 py-1 text-xs font-medium border rounded transition-colors disabled:opacity-50 disabled:cursor-not-allowed ${
          isUsingCustomSelection
            ? "bg-primary/10 border-primary text-primary"
            : "bg-card border-border text-foreground"
        }`}
        title={`Current model: ${currentModelLabel} (${currentModel}) - ${currentProvider}${isUsingCustomSelection ? " - Custom selection" : " - Default"}`}
      >
        <span>Model:</span>
        <span className="font-semibold">{currentModelLabel}</span>
        <ChevronDown className={`w-3 h-3 transition-transform ${isOpen ? "rotate-180" : ""}`} />
      </button>

      {isOpen && coords && (
        <ModelDropdown
          providers={providers}
          currentProvider={currentProvider}
          currentModel={currentModel}
          defaultModel={defaultModel}
          conversationCapabilities={conversationCapabilities}
          showCapabilities={showCapabilities}
          showMakeDefault={showMakeDefault}
          isUpdatingDefault={isUpdatingDefault}
          isCurrentSelectionDefault={isCurrentSelectionDefault}
          isUsingCustomSelection={!!isUsingCustomSelection}
          coords={coords}
          position={position}
          verticalPosition={verticalPosition}
          searchInputRef={searchInputRef}
          selectedModelRef={selectedModelRef}
          onSelect={handleModelSelect}
          onMakeDefault={handleMakeDefault}
          onClose={close}
        />
      )}
    </div>
  );
}
