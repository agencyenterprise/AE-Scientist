import { useCallback, useEffect, useState } from "react";

import { apiFetch } from "@/shared/lib/api-client";
import type { ResearchGpuTypesResponse } from "@/types";

interface UseGpuSelectionResult {
  gpuTypes: string[];
  selectedGpuType: string | null;
  isGpuTypeLoading: boolean;
  refreshGpuTypes: () => Promise<void>;
  setSelectedGpuType: (gpuType: string) => void;
}

export function useGpuSelection(): UseGpuSelectionResult {
  const [gpuTypes, setGpuTypes] = useState<string[]>([]);
  const [selectedGpuType, setSelectedGpuType] = useState<string | null>(null);
  const [isGpuTypeLoading, setIsGpuTypeLoading] = useState(true);

  const refreshGpuTypes = useCallback(async (): Promise<void> => {
    setIsGpuTypeLoading(true);
    try {
      const response = await apiFetch<ResearchGpuTypesResponse>(
        "/conversations/research/gpu-types"
      );
      const list = response.gpu_types ?? [];
      setGpuTypes(list);
      setSelectedGpuType(previous => {
        if (previous && list.includes(previous)) {
          return previous;
        }
        const [preferredGpu] = list;
        const fallbackGpu: string | null = preferredGpu ?? null;
        return fallbackGpu;
      });
    } catch (error) {
      // eslint-disable-next-line no-console
      console.error("Failed to load GPU types", error);
      setGpuTypes([]);
      setSelectedGpuType(null);
    } finally {
      setIsGpuTypeLoading(false);
    }
  }, []);

  useEffect(() => {
    void refreshGpuTypes();
  }, [refreshGpuTypes]);

  const handleSelectGpuType = useCallback((gpuType: string): void => {
    setSelectedGpuType(gpuType);
  }, []);

  return {
    gpuTypes,
    selectedGpuType,
    isGpuTypeLoading,
    refreshGpuTypes,
    setSelectedGpuType: handleSelectGpuType,
  };
}
