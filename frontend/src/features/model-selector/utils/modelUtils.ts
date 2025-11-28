import type { LLMDefault, LLMModel } from "@/types";

/**
 * Capabilities required by a conversation (e.g., if it contains images or PDFs).
 */
export interface ConversationCapabilities {
  /** Whether the conversation contains images */
  hasImages?: boolean;
  /** Whether the conversation contains PDFs */
  hasPdfs?: boolean;
}

/**
 * Capabilities supported by a model.
 */
export interface ModelCapabilities {
  /** Whether the model supports image inputs */
  supportsImages: boolean;
  /** Whether the model supports PDF inputs */
  supportsPdfs: boolean;
}

/**
 * Gets the human-readable label for a model.
 * Falls back to the model ID if the model is not found.
 *
 * @param providers - Map of provider names to their available models
 * @param provider - The provider name (e.g., "openai", "anthropic")
 * @param modelId - The model identifier
 * @returns The model's display label or the modelId if not found
 */
export function getModelLabel(
  providers: Record<string, LLMModel[]>,
  provider: string,
  modelId: string
): string {
  const providerModels = providers[provider];
  if (!providerModels) return modelId;

  const model = providerModels.find(m => m.id === modelId);
  return model ? model.label : modelId;
}

/**
 * Checks if a model is the current default for a prompt type.
 *
 * @param defaultModel - The current default model configuration
 * @param provider - The provider name to check
 * @param model - The model ID to check
 * @returns True if the model matches the default
 */
export function isModelDefault(
  defaultModel: LLMDefault | null,
  provider: string,
  model: string
): boolean {
  return defaultModel?.llm_provider === provider && defaultModel?.llm_model === model;
}

/**
 * Checks if a model is compatible with the conversation's capability requirements.
 * A model is compatible if it supports all the capabilities the conversation needs.
 *
 * @param providers - Map of provider names to their available models
 * @param provider - The provider name
 * @param modelId - The model identifier
 * @param capabilities - The capabilities required by the conversation
 * @returns True if the model supports all required capabilities
 */
export function isModelCompatible(
  providers: Record<string, LLMModel[]>,
  provider: string,
  modelId: string,
  capabilities?: ConversationCapabilities
): boolean {
  if (!capabilities) return true;

  const providerModels = providers[provider];
  if (!providerModels) return true;

  const model = providerModels.find(m => m.id === modelId);
  if (!model) return true;

  if (capabilities.hasImages && !model.supports_images) return false;
  if (capabilities.hasPdfs && !model.supports_pdfs) return false;

  return true;
}

/**
 * Gets a human-readable reason why a model is incompatible with the conversation.
 * Returns null if the model is compatible.
 *
 * @param providers - Map of provider names to their available models
 * @param provider - The provider name
 * @param modelId - The model identifier
 * @param capabilities - The capabilities required by the conversation
 * @returns A string describing what the model doesn't support, or null if compatible
 */
export function getIncompatibilityReason(
  providers: Record<string, LLMModel[]>,
  provider: string,
  modelId: string,
  capabilities?: ConversationCapabilities
): string | null {
  if (!capabilities || isModelCompatible(providers, provider, modelId, capabilities)) {
    return null;
  }

  const providerModels = providers[provider];
  if (!providerModels) return null;

  const model = providerModels.find(m => m.id === modelId);
  if (!model) return null;

  const missing: string[] = [];
  if (capabilities.hasImages && !model.supports_images) missing.push("images");
  if (capabilities.hasPdfs && !model.supports_pdfs) missing.push("PDFs");

  return `Doesn't support ${missing.join(" or ")}`;
}

/**
 * Gets the capabilities supported by a specific model.
 *
 * @param providers - Map of provider names to their available models
 * @param provider - The provider name
 * @param model - The model identifier
 * @returns The model's capabilities (defaults to false for both if model not found)
 */
export function getModelCapabilities(
  providers: Record<string, LLMModel[]>,
  provider: string,
  model: string
): ModelCapabilities {
  const defaultCapabilities = { supportsImages: false, supportsPdfs: false };

  if (!model || !provider) return defaultCapabilities;

  const providerModels = providers[provider];
  if (!providerModels) return defaultCapabilities;

  const foundModel = providerModels.find(m => m.id === model);
  if (!foundModel) return defaultCapabilities;

  return {
    supportsImages: foundModel.supports_images || false,
    supportsPdfs: foundModel.supports_pdfs || false,
  };
}

/**
 * Finds the first model that is compatible with the given capability requirements.
 * Iterates through all providers and their models in order.
 *
 * @param providers - Map of provider names to their available models
 * @param capabilities - The capabilities required by the conversation
 * @returns The first compatible provider/model pair, or null if none found
 */
export function findFirstCompatibleModel(
  providers: Record<string, LLMModel[]>,
  capabilities?: ConversationCapabilities
): { provider: string; model: string } | null {
  for (const [provider, models] of Object.entries(providers)) {
    for (const model of models) {
      if (isModelCompatible(providers, provider, model.id, capabilities)) {
        return { provider, model: model.id };
      }
    }
  }
  return null;
}

/**
 * Filters providers and models based on a search text.
 * If a provider name matches, all its models are included.
 * Otherwise, only models whose label or ID match are included.
 *
 * @param providers - Map of provider names to their available models
 * @param filterText - The search text to filter by
 * @returns Filtered map of providers to matching models
 */
export function filterProviders(
  providers: Record<string, LLMModel[]>,
  filterText: string
): Record<string, LLMModel[]> {
  if (!filterText.trim()) {
    return providers;
  }

  const searchText = filterText.toLowerCase().trim();
  const filtered: Record<string, LLMModel[]> = {};

  Object.entries(providers).forEach(([provider, models]) => {
    const providerMatches = provider.toLowerCase().includes(searchText);
    const matchingModels = models.filter(
      model =>
        model.label.toLowerCase().includes(searchText) ||
        model.id.toLowerCase().includes(searchText)
    );

    if (providerMatches || matchingModels.length > 0) {
      filtered[provider] = providerMatches ? models : matchingModels;
    }
  });

  return filtered;
}
