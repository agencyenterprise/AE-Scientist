import { useState, useCallback } from "react";

interface ModelSelectionState {
  selectedModel: string;
  selectedProvider: string;
  currentModel: string;
  currentProvider: string;
  modelCapabilities: {
    supportsImages: boolean;
    supportsPdfs: boolean;
  };
}

interface ModelSelectionActions {
  handleModelChange: (model: string, provider: string) => void;
  handleModelDefaults: (model: string, provider: string) => void;
  handleModelCapabilities: (capabilities: {
    supportsImages: boolean;
    supportsPdfs: boolean;
  }) => void;
}

export function useModelSelection(): ModelSelectionState & ModelSelectionActions {
  const [selectedModel, setSelectedModel] = useState<string>("");
  const [selectedProvider, setSelectedProvider] = useState<string>("");
  const [currentModel, setCurrentModel] = useState<string>("");
  const [currentProvider, setCurrentProvider] = useState<string>("");
  const [modelCapabilities, setModelCapabilities] = useState<{
    supportsImages: boolean;
    supportsPdfs: boolean;
  }>({ supportsImages: false, supportsPdfs: false });

  const handleModelChange = useCallback((model: string, provider: string): void => {
    // Update both selected (for custom selections) and current (for sending requests)
    if (model && provider) {
      // User made a custom selection
      setSelectedModel(model);
      setSelectedProvider(provider);
      setCurrentModel(model);
      setCurrentProvider(provider);
    } else {
      // User cleared custom selection, will use defaults
      setSelectedModel("");
      setSelectedProvider("");
      // currentModel/currentProvider will be set by ModelSelector when defaults load
    }
  }, []);

  const handleModelDefaults = useCallback(
    (model: string, provider: string): void => {
      // Called by ModelSelector when defaults are loaded or when selection falls back to defaults
      if (!selectedModel && !selectedProvider) {
        // Only update current if no custom selection
        setCurrentModel(model);
        setCurrentProvider(provider);
      }
    },
    [selectedModel, selectedProvider]
  );

  const handleModelCapabilities = useCallback(
    (capabilities: { supportsImages: boolean; supportsPdfs: boolean }): void => {
      setModelCapabilities(capabilities);
    },
    []
  );

  return {
    selectedModel,
    selectedProvider,
    currentModel,
    currentProvider,
    modelCapabilities,
    handleModelChange,
    handleModelDefaults,
    handleModelCapabilities,
  };
}
