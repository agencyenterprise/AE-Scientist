import { config } from "@/shared/lib/config";
import type { LLMDefault, LLMDefaultsResponse, LLMModel, LLMProvidersResponse } from "@/types";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

/**
 * Props for the useModelSelectorData hook.
 */
interface UseModelSelectorDataProps {
  /** The prompt type to fetch defaults for (e.g., "idea_generation", "idea_chat") */
  promptType: string;
}

/**
 * Result from updating the default model.
 */
interface UpdateDefaultResult {
  /** The newly updated default model configuration */
  updated_default: LLMDefault;
}

/**
 * Return type for the useModelSelectorData hook.
 */
interface UseModelSelectorDataReturn {
  /** The current default model for this prompt type, or null if loading */
  defaultModel: LLMDefault | null;
  /** Map of provider names to their available models */
  providers: Record<string, LLMModel[]>;
  /** True while initial data is being fetched */
  isLoading: boolean;
  /** Function to update the default model for this prompt type */
  updateDefault: (provider: string, model: string) => Promise<LLMDefault>;
  /** True while a default update mutation is in progress */
  isUpdatingDefault: boolean;
}

/**
 * Fetches the default model configuration for a prompt type.
 * @internal
 */
async function fetchDefaults(promptType: string): Promise<LLMDefaultsResponse> {
  const response = await fetch(`${config.apiUrl}/llm-defaults/${promptType}`, {
    credentials: "include",
  });
  if (!response.ok) {
    throw new Error("Failed to fetch LLM defaults");
  }
  return response.json();
}

/**
 * Fetches all available LLM providers and their models.
 * @internal
 */
async function fetchProviders(): Promise<LLMProvidersResponse> {
  const response = await fetch(`${config.apiUrl}/llm-defaults/providers`, {
    credentials: "include",
  });
  if (!response.ok) {
    throw new Error("Failed to fetch LLM providers");
  }
  return response.json();
}

/**
 * Updates the default model for a prompt type via the API.
 * @internal
 */
async function updateDefaultModel(
  promptType: string,
  provider: string,
  model: string
): Promise<UpdateDefaultResult> {
  const response = await fetch(`${config.apiUrl}/llm-defaults/${promptType}`, {
    method: "PUT",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      llm_provider: provider,
      llm_model: model,
    }),
  });
  if (!response.ok) {
    throw new Error("Failed to update default model");
  }
  return response.json();
}

/**
 * React Query hook for fetching and managing LLM model selector data.
 *
 * Provides:
 * - Default model configuration for a specific prompt type
 * - Available providers and their models (cached for 5 minutes)
 * - Mutation to update the default model
 *
 * @param props - Hook configuration
 * @param props.promptType - The prompt type to fetch defaults for
 * @returns Object containing model data, loading states, and update function
 *
 * @example
 * ```tsx
 * const { defaultModel, providers, isLoading, updateDefault } = useModelSelectorData({
 *   promptType: "idea_generation"
 * });
 * ```
 */
export function useModelSelectorData({
  promptType,
}: UseModelSelectorDataProps): UseModelSelectorDataReturn {
  const queryClient = useQueryClient();

  const defaultsQuery = useQuery({
    queryKey: ["llm-defaults", promptType],
    queryFn: () => fetchDefaults(promptType),
  });

  const providersQuery = useQuery({
    queryKey: ["llm-providers"],
    queryFn: fetchProviders,
    staleTime: 5 * 60 * 1000, // Cache for 5 minutes
  });

  const updateMutation = useMutation({
    mutationFn: ({ provider, model }: { provider: string; model: string }) =>
      updateDefaultModel(promptType, provider, model),
    onSuccess: data => {
      queryClient.setQueryData(["llm-defaults", promptType], {
        current_default: data.updated_default,
      });
    },
  });

  const updateDefault = async (provider: string, model: string): Promise<LLMDefault> => {
    const result = await updateMutation.mutateAsync({ provider, model });
    return result.updated_default;
  };

  return {
    defaultModel: defaultsQuery.data?.current_default ?? null,
    providers: providersQuery.data?.providers ?? {},
    isLoading: defaultsQuery.isLoading || providersQuery.isLoading,
    updateDefault,
    isUpdatingDefault: updateMutation.isPending,
  };
}
