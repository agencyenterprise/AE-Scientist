import { useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/shared/lib/api-client-typed";
import {
  getInsufficientBalanceDetail,
  formatInsufficientBalanceMessage,
} from "@/shared/utils/costs";
import { useGpuSelection } from "@/features/research/hooks/useGpuSelection";

/**
 * Custom hook for launching research from an idea
 * Handles modal state, API calls, and error handling
 */
export function useLaunchResearch(conversationId: number | null) {
  const router = useRouter();
  const [isLaunchModalOpen, setIsLaunchModalOpen] = useState(false);
  const [isLaunching, setIsLaunching] = useState(false);
  const {
    gpuTypes,
    gpuPrices,
    gpuDisplayNames,
    gpuVramGb,
    selectedGpuType,
    isGpuTypeLoading,
    refreshGpuTypes,
    setSelectedGpuType,
  } = useGpuSelection();

  const handleLaunchClick = () => {
    void refreshGpuTypes();
    setIsLaunchModalOpen(true);
  };

  const handleConfirmLaunch = async (): Promise<void> => {
    if (!conversationId) return;
    if (!selectedGpuType) {
      throw new Error("Select a GPU type before launching research.");
    }
    setIsLaunching(true);
    try {
      const { data, error, response } = await api.POST(
        "/api/conversations/{conversation_id}/idea/research-run",
        {
          params: { path: { conversation_id: conversationId } },
          body: { gpu_type: selectedGpuType },
        }
      );
      if (error) {
        if (response.status === 402) {
          // 402 response is typed as InsufficientBalanceError from the OpenAPI schema
          const detail = getInsufficientBalanceDetail(error);
          throw new Error(formatInsufficientBalanceMessage(detail));
        }
        if (response.status === 400) {
          const errorObj = error as unknown as Record<string, unknown>;
          const detailValue =
            errorObj && typeof errorObj.detail === "string" ? errorObj.detail : undefined;
          const message = detailValue ?? "Failed to launch research run.";
          throw new Error(message);
        }
        throw new Error("Failed to launch research run");
      }
      setIsLaunchModalOpen(false);
      router.push(`/research/${data.run_id}`);
    } finally {
      setIsLaunching(false);
    }
  };

  return {
    isLaunchModalOpen,
    setIsLaunchModalOpen,
    isLaunching,
    handleLaunchClick,
    handleConfirmLaunch,
    gpuTypes,
    gpuPrices,
    gpuDisplayNames,
    gpuVramGb,
    selectedGpuType,
    isGpuTypeLoading,
    setSelectedGpuType,
  };
}
