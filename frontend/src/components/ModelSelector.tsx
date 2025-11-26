"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { config } from "@/lib/config";
import type {
  LLMDefault,
  LLMDefaultsResponse,
  LLMDefaultsUpdateRequest,
  LLMProvidersResponse,
  LLMModel,
} from "@/types";

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
  conversationCapabilities?: {
    hasImages?: boolean;
    hasPdfs?: boolean;
  };
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
  const [isLoading, setIsLoading] = useState(true);
  const [isOpen, setIsOpen] = useState(false);
  const [defaultModel, setDefaultModel] = useState<LLMDefault | null>(null);
  const [availableProviders, setAvailableProviders] = useState<Record<string, LLMModel[]>>({});
  const [isUpdatingDefault, setIsUpdatingDefault] = useState(false);
  const [dropdownPosition, setDropdownPosition] = useState<"left" | "right">("left");
  const [dropdownCoords, setDropdownCoords] = useState<{
    top: number;
    left: number;
    right: number;
  } | null>(null);
  const [filterText, setFilterText] = useState("");
  const buttonRef = useRef<HTMLButtonElement>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);
  const selectedModelRef = useRef<HTMLButtonElement>(null);

  // Get current selection (from props or defaults)
  const currentProvider = selectedProvider || defaultModel?.llm_provider || "";
  const currentModel = selectedModel || defaultModel?.llm_model || "";

  // Check if a model is the current default
  const isModelDefault = (provider: string, model: string): boolean => {
    return defaultModel?.llm_provider === provider && defaultModel?.llm_model === model;
  };

  // Get the label for a model ID within a provider
  const getModelLabel = (provider: string, modelId: string): string => {
    const providerModels = availableProviders[provider];
    if (!providerModels) return modelId;

    const model = providerModels.find(m => m.id === modelId);
    return model ? model.label : modelId;
  };

  // Get the display label for the current model
  const currentModelLabel =
    currentModel && currentProvider ? getModelLabel(currentProvider, currentModel) : "Default";

  // Get current model capabilities
  const getCurrentModelCapabilities = useCallback((): {
    supportsImages: boolean;
    supportsPdfs: boolean;
  } => {
    if (!currentModel || !currentProvider) {
      return { supportsImages: false, supportsPdfs: false };
    }

    const providerModels = availableProviders[currentProvider];
    if (!providerModels) {
      return { supportsImages: false, supportsPdfs: false };
    }

    const model = providerModels.find(m => m.id === currentModel);
    if (!model) {
      return { supportsImages: false, supportsPdfs: false };
    }

    return {
      supportsImages: model.supports_images || false,
      supportsPdfs: model.supports_pdfs || false,
    };
  }, [currentModel, currentProvider, availableProviders]);

  // Check if a model supports conversation requirements
  const isModelCompatible = useCallback(
    (provider: string, modelId: string): boolean => {
      if (!conversationCapabilities) return true; // No requirements = all compatible

      const providerModels = availableProviders[provider];
      if (!providerModels) return true;

      const model = providerModels.find(m => m.id === modelId);
      if (!model) return true;

      if (conversationCapabilities.hasImages && !model.supports_images) return false;
      if (conversationCapabilities.hasPdfs && !model.supports_pdfs) return false;

      return true;
    },
    [conversationCapabilities, availableProviders]
  );

  // Get incompatibility reason for display
  const getIncompatibilityReason = (provider: string, modelId: string): string | null => {
    if (!conversationCapabilities || isModelCompatible(provider, modelId)) return null;

    const providerModels = availableProviders[provider];
    if (!providerModels) return null;

    const model = providerModels.find(m => m.id === modelId);
    if (!model) return null;

    const missing = [];
    if (conversationCapabilities.hasImages && !model.supports_images) missing.push("images");
    if (conversationCapabilities.hasPdfs && !model.supports_pdfs) missing.push("PDFs");

    return `Doesn't support ${missing.join(" or ")}`;
  };

  // Find first compatible model for auto-selection
  const findFirstCompatibleModel = useCallback((): {
    provider: string;
    model: string;
  } | null => {
    for (const [provider, models] of Object.entries(availableProviders)) {
      for (const model of models) {
        if (isModelCompatible(provider, model.id)) {
          return { provider, model: model.id };
        }
      }
    }
    return null;
  }, [availableProviders, isModelCompatible]);

  // Filter providers and models based on search text
  const filteredProviders = useMemo((): Record<string, LLMModel[]> => {
    if (!filterText.trim()) {
      return availableProviders;
    }

    const searchText = filterText.toLowerCase().trim();
    const filtered: Record<string, LLMModel[]> = {};

    Object.entries(availableProviders).forEach(([provider, models]) => {
      // Check if provider name matches
      const providerMatches = provider.toLowerCase().includes(searchText);

      // Filter models that match the search text
      const matchingModels = models.filter(
        model =>
          model.label.toLowerCase().includes(searchText) ||
          model.id.toLowerCase().includes(searchText)
      );

      // Include provider if it matches or has matching models
      if (providerMatches || matchingModels.length > 0) {
        // If provider matches, include all models; otherwise only matching models
        filtered[provider] = providerMatches ? models : matchingModels;
      }
    });

    return filtered;
  }, [availableProviders, filterText]);

  // Notify parent whenever the effective current model changes
  useEffect(() => {
    if (currentModel && currentProvider) {
      onDefaultsChange?.(currentModel, currentProvider);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentModel, currentProvider]);

  // Notify parent whenever model capabilities change
  useEffect(() => {
    if (currentModel && currentProvider && Object.keys(availableProviders).length > 0) {
      const capabilities = getCurrentModelCapabilities();
      onCapabilitiesChange?.(capabilities);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentModel, currentProvider, availableProviders]);

  // Load default model and available providers
  useEffect(() => {
    const loadData = async (): Promise<void> => {
      setIsLoading(true);

      // Load both defaults and providers in parallel
      const [defaultsResponse, providersResponse] = await Promise.all([
        fetch(`${config.apiUrl}/llm-defaults/${promptType}`, { credentials: "include" }),
        fetch(`${config.apiUrl}/llm-defaults/providers`, { credentials: "include" }),
      ]);

      // Load defaults
      if (defaultsResponse.ok) {
        const defaultsData: LLMDefaultsResponse = await defaultsResponse.json();
        setDefaultModel(defaultsData.current_default);
      }

      // Load providers
      if (providersResponse.ok) {
        const providersData: LLMProvidersResponse = await providersResponse.json();
        setAvailableProviders(providersData.providers);
      }

      setIsLoading(false);
    };

    loadData();
  }, [promptType]);

  // Auto-select compatible model if default is incompatible
  useEffect(() => {
    if (!defaultModel || !conversationCapabilities || Object.keys(availableProviders).length === 0)
      return;

    // Check if current selection (or default) is compatible
    const currentProvider = selectedProvider || defaultModel.llm_provider;
    const currentModel = selectedModel || defaultModel.llm_model;

    if (!isModelCompatible(currentProvider, currentModel)) {
      // Default is incompatible, auto-select first compatible model
      const compatible = findFirstCompatibleModel();
      if (compatible) {
        onModelChange?.(compatible.model, compatible.provider);
      }
    }
  }, [
    defaultModel,
    conversationCapabilities,
    availableProviders,
    selectedModel,
    selectedProvider,
    isModelCompatible,
    findFirstCompatibleModel,
    onModelChange,
  ]);

  // Recalculate position on window resize
  useEffect(() => {
    const handleResize = (): void => {
      if (isOpen && dropdownCoords) {
        calculateDropdownPosition();
      }
    };

    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, [isOpen, dropdownCoords]);

  const calculateDropdownPosition = (): void => {
    if (!buttonRef.current) return;

    const buttonRect = buttonRef.current.getBoundingClientRect();
    const dropdownWidth = 256; // w-64 = 16rem = 256px
    const viewportWidth = window.innerWidth;
    const spaceOnRight = viewportWidth - buttonRect.right;

    // Calculate position coordinates for fixed positioning
    const top = buttonRect.bottom + 4; // 4px margin (mt-1)

    // If there's not enough space on the right, position to the right edge
    if (spaceOnRight < dropdownWidth) {
      setDropdownPosition("right");
      setDropdownCoords({
        top,
        left: 0,
        right: viewportWidth - buttonRect.right,
      });
    } else {
      setDropdownPosition("left");
      setDropdownCoords({
        top,
        left: buttonRect.left,
        right: 0,
      });
    }
  };

  const handleToggleOpen = (): void => {
    if (!isOpen) {
      calculateDropdownPosition();
      // Focus search input and scroll to selected model after dropdown opens
      setTimeout(() => {
        searchInputRef.current?.focus();
        // Scroll to selected model if it exists and is visible
        selectedModelRef.current?.scrollIntoView({
          behavior: "smooth",
          block: "center",
        });
      }, 50); // Small delay to ensure DOM has updated
    } else {
      setDropdownCoords(null);
      // Clear filter when closing dropdown
      setFilterText("");
    }
    setIsOpen(!isOpen);
  };

  const handleModelSelect = (provider: string, model: string): void => {
    // Check if model is compatible with conversation requirements
    if (!isModelCompatible(provider, model)) {
      // Don't allow selection of incompatible models
      return;
    }

    // Don't close dropdown automatically - let user choose to make it default
    onModelChange?.(model, provider);
  };

  const handleMakeDefault = async (): Promise<void> => {
    if (!currentModel || !currentProvider) return;

    setIsUpdatingDefault(true);

    try {
      const updateRequest: LLMDefaultsUpdateRequest = {
        llm_provider: currentProvider,
        llm_model: currentModel,
      };

      const response = await fetch(`${config.apiUrl}/llm-defaults/${promptType}`, {
        method: "PUT",
        credentials: "include", // Include authentication cookies
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(updateRequest),
      });

      if (response.ok) {
        const result = await response.json();
        setDefaultModel(result.updated_default);
        // Clear any temporary selection since it's now the default
        onModelChange?.("", "");
        // Notify parent about the new current model (which is now the default)
        onDefaultsChange?.(result.updated_default.llm_model, result.updated_default.llm_provider);
        // Close dropdown after successful default update
        setIsOpen(false);
        setDropdownCoords(null);
        setFilterText("");
      }
    } finally {
      setIsUpdatingDefault(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center space-x-2 text-xs text-gray-500">
        <div className="animate-spin rounded-full h-3 w-3 border-b-2 border-gray-400"></div>
        <span>Loading...</span>
      </div>
    );
  }

  // Check if current selection differs from default
  const isUsingCustomSelection =
    (selectedModel && selectedModel !== defaultModel?.llm_model) ||
    (selectedProvider && selectedProvider !== defaultModel?.llm_provider);

  // Check if current selection is already the default
  const isCurrentSelectionDefault = isModelDefault(currentProvider, currentModel);

  return (
    <div className="relative">
      <button
        type="button"
        ref={buttonRef}
        onClick={handleToggleOpen}
        disabled={disabled}
        className="flex items-center space-x-1 px-2 py-1 text-xs font-medium border rounded transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        style={{
          backgroundColor: isUsingCustomSelection ? "#dbeafe" : "white",
          borderColor: isUsingCustomSelection ? "#3b82f6" : "#d1d5db",
          color: isUsingCustomSelection ? "#1d4ed8" : "#374151",
        }}
        title={`Current model: ${currentModelLabel} (${currentModel}) - ${currentProvider}${isUsingCustomSelection ? " - Custom selection" : " - Default"}`}
      >
        <span>Model:</span>
        <span className="font-semibold">{currentModelLabel}</span>
        <svg
          className={`w-3 h-3 transition-transform ${isOpen ? "rotate-180" : ""}`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {isOpen && dropdownCoords && (
        <>
          {/* Backdrop */}
          <div
            className="fixed inset-0 z-[55]"
            onClick={() => {
              setIsOpen(false);
              setDropdownCoords(null);
              setFilterText("");
            }}
          />

          {/* Dropdown */}
          <div
            className="fixed w-64 bg-white border border-gray-200 rounded-md shadow-lg z-[60]"
            style={{
              top: dropdownCoords?.top || 0,
              left: dropdownPosition === "left" ? dropdownCoords?.left || 0 : "auto",
              right: dropdownPosition === "right" ? dropdownCoords?.right || 0 : "auto",
            }}
          >
            {/* Header with close button */}
            <div className="flex items-center justify-between px-3 py-2 border-b border-gray-100 bg-gray-50">
              <span className="text-xs font-semibold text-gray-700 uppercase tracking-wide">
                Select Model
              </span>
              <button
                type="button"
                onClick={() => {
                  setIsOpen(false);
                  setDropdownCoords(null);
                  setFilterText("");
                }}
                className="text-gray-400 hover:text-gray-600 p-0.5 rounded transition-colors"
                title="Close"
              >
                <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M6 18L18 6M6 6l12 12"
                  />
                </svg>
              </button>
            </div>

            {/* Search Input */}
            <div className="p-2 border-b border-gray-100">
              <input
                ref={searchInputRef}
                type="text"
                placeholder="Search models..."
                value={filterText}
                onChange={e => setFilterText(e.target.value)}
                className="w-full px-2 py-1 text-xs border border-gray-200 rounded focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
                onClick={e => e.stopPropagation()}
                onKeyDown={e => {
                  // Prevent dropdown from closing on Enter
                  if (e.key === "Enter") {
                    e.preventDefault();
                  }
                }}
              />
            </div>

            <div className="max-h-64 overflow-y-auto">
              {Object.keys(filteredProviders).length === 0 && filterText.trim() ? (
                <div className="p-4 text-center text-xs text-gray-500">
                  <div className="mb-1">No models found</div>
                  <div>Try adjusting your search</div>
                </div>
              ) : (
                Object.entries(filteredProviders).map(([provider, models]) => (
                  <div key={provider} className="border-b border-gray-100 last:border-b-0">
                    <div className="px-3 py-2 bg-gray-50 text-xs font-semibold text-gray-700 uppercase tracking-wide">
                      {provider}
                    </div>
                    {models.map(model => {
                      const isSelected = currentProvider === provider && currentModel === model.id;
                      const isDefault = isModelDefault(provider, model.id);
                      const isCompatible = isModelCompatible(provider, model.id);
                      const incompatibilityReason = getIncompatibilityReason(provider, model.id);

                      return (
                        <button
                          type="button"
                          key={`${provider}-${model.id}`}
                          ref={isSelected ? selectedModelRef : null}
                          onClick={() => handleModelSelect(provider, model.id)}
                          disabled={!isCompatible}
                          className={`w-full text-left px-3 py-2 text-xs transition-colors ${
                            !isCompatible
                              ? "text-gray-400 cursor-not-allowed opacity-75"
                              : isSelected
                                ? "bg-blue-50 text-blue-700 font-medium hover:bg-blue-100"
                                : isDefault
                                  ? "bg-green-50 hover:bg-green-100 border-l-2 border-green-300"
                                  : "text-gray-700 hover:bg-gray-50"
                          }`}
                          title={incompatibilityReason || undefined}
                        >
                          <div className="flex items-center">
                            {/* Model name - flexible width */}
                            <div className="flex-1 min-w-0 pr-2">
                              <div className="truncate">{model.label}</div>
                              {isDefault && (
                                <div className="text-xs text-green-600 font-medium">default</div>
                              )}
                              {incompatibilityReason && (
                                <div className="text-xs text-gray-400 italic truncate">
                                  {incompatibilityReason}
                                </div>
                              )}
                            </div>

                            {/* Capabilities - fixed width for alignment */}
                            {showCapabilities && (
                              <div className="flex items-center justify-center w-12 space-x-0.5">
                                <span title="Supports images" className="text-xs w-4 text-center">
                                  {model.supports_images ? "🖼️" : ""}
                                </span>
                                <span title="Supports PDFs" className="text-xs w-4 text-center">
                                  {model.supports_pdfs ? "📄" : ""}
                                </span>
                              </div>
                            )}

                            {/* Selection checkmark - small fixed width on right */}
                            <div className="flex items-center justify-center w-8">
                              {isSelected && (
                                <span className={isCompatible ? "text-blue-500" : "text-gray-400"}>
                                  ✓
                                </span>
                              )}
                            </div>
                          </div>
                        </button>
                      );
                    })}
                  </div>
                ))
              )}
            </div>

            {/* Make Default / Already Default section */}
            {showMakeDefault && (
              <div className="border-t border-gray-200 p-2">
                {isCurrentSelectionDefault ? (
                  <div className="flex items-center justify-center space-x-1 px-2 py-1.5 text-xs font-medium text-green-700 bg-green-50 rounded">
                    <span>✓</span>
                    <span>Already Default</span>
                  </div>
                ) : isUsingCustomSelection ? (
                  <button
                    type="button"
                    onClick={handleMakeDefault}
                    disabled={isUpdatingDefault}
                    className="w-full flex items-center justify-center space-x-1 px-2 py-1.5 text-xs font-medium text-blue-600 hover:text-blue-800 hover:bg-blue-50 rounded transition-colors disabled:opacity-50"
                  >
                    {isUpdatingDefault ? (
                      <>
                        <div className="animate-spin rounded-full h-3 w-3 border-b-2 border-blue-600"></div>
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
        </>
      )}
    </div>
  );
}
