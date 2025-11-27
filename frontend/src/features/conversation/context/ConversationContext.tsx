"use client";

import { createContext, useContext, ReactNode, useState, useMemo, useCallback } from "react";
import { useModelSelection } from "@/features/project-draft/hooks/useModelSelection";

interface ModelCapabilities {
  supportsImages: boolean;
  supportsPdfs: boolean;
}

interface EffectiveCapabilities {
  hasImages?: boolean;
  hasPdfs?: boolean;
}

export interface ConversationContextValue {
  // Model selection state (lifted to provider level)
  selectedModel: string;
  selectedProvider: string;
  currentModel: string;
  currentProvider: string;
  modelCapabilities: ModelCapabilities;

  // Model selection actions
  handleModelChange: (model: string, provider: string) => void;
  handleModelDefaults: (model: string, provider: string) => void;
  handleModelCapabilities: (capabilities: ModelCapabilities) => void;

  // Dynamic state (set by children, read by header)
  effectiveCapabilities: EffectiveCapabilities;
  setEffectiveCapabilities: (caps: EffectiveCapabilities) => void;
  isStreaming: boolean;
  setIsStreaming: (streaming: boolean) => void;
  isReadOnly: boolean;
  setIsReadOnly: (readOnly: boolean) => void;

  // Prompt modal
  onOpenPromptModal?: () => void;
  setOnOpenPromptModal: (handler: (() => void) | undefined) => void;
}

const ConversationContext = createContext<ConversationContextValue | null>(null);

export function useConversationContext() {
  const context = useContext(ConversationContext);
  if (!context) {
    throw new Error("useConversationContext must be used within ConversationProvider");
  }
  return context;
}

interface ConversationProviderProps {
  children: ReactNode;
}

export function ConversationProvider({ children }: ConversationProviderProps) {
  // Lift model selection to provider level
  const {
    selectedModel,
    selectedProvider,
    currentModel,
    currentProvider,
    modelCapabilities,
    handleModelChange,
    handleModelDefaults,
    handleModelCapabilities,
  } = useModelSelection();

  // Dynamic state that children can set
  const [effectiveCapabilities, setEffectiveCapabilities] = useState<EffectiveCapabilities>({});
  const [isStreaming, setIsStreaming] = useState(false);
  const [isReadOnly, setIsReadOnly] = useState(false);
  const [onOpenPromptModal, setOnOpenPromptModal] = useState<(() => void) | undefined>(undefined);

  // Wrap setOnOpenPromptModal to handle function values correctly
  const setOnOpenPromptModalWrapper = useCallback((handler: (() => void) | undefined) => {
    setOnOpenPromptModal(() => handler);
  }, []);

  const value = useMemo<ConversationContextValue>(
    () => ({
      selectedModel,
      selectedProvider,
      currentModel,
      currentProvider,
      modelCapabilities,
      handleModelChange,
      handleModelDefaults,
      handleModelCapabilities,
      effectiveCapabilities,
      setEffectiveCapabilities,
      isStreaming,
      setIsStreaming,
      isReadOnly,
      setIsReadOnly,
      onOpenPromptModal,
      setOnOpenPromptModal: setOnOpenPromptModalWrapper,
    }),
    [
      selectedModel,
      selectedProvider,
      currentModel,
      currentProvider,
      modelCapabilities,
      handleModelChange,
      handleModelDefaults,
      handleModelCapabilities,
      effectiveCapabilities,
      isStreaming,
      isReadOnly,
      onOpenPromptModal,
      setOnOpenPromptModalWrapper,
    ]
  );

  return <ConversationContext.Provider value={value}>{children}</ConversationContext.Provider>;
}
