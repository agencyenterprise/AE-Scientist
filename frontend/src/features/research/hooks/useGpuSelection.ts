import { useCallback, useEffect, useState } from "react";

import { api } from "@/shared/lib/api-client-typed";
import type { ResearchGpuTypesResponse } from "@/types";

interface UseGpuSelectionResult {
  gpuTypes: string[];
  gpuPrices: Record<string, number | null>;
  gpuDisplayNames: Record<string, string>;
  gpuVramGb: Record<string, number | null>;
  selectedGpuType: string | null;
  isGpuTypeLoading: boolean;
  refreshGpuTypes: () => Promise<void>;
  setSelectedGpuType: (gpuType: string) => void;
}

export function useGpuSelection(): UseGpuSelectionResult {
  const [gpuTypes, setGpuTypes] = useState<string[]>([]);
  const [gpuPrices, setGpuPrices] = useState<Record<string, number | null>>({});
  const [gpuDisplayNames, setGpuDisplayNames] = useState<Record<string, string>>({});
  const [gpuVramGb, setGpuVramGb] = useState<Record<string, number | null>>({});
  const [selectedGpuType, setSelectedGpuType] = useState<string | null>(null);
  const [isGpuTypeLoading, setIsGpuTypeLoading] = useState(true);

  const refreshGpuTypes = useCallback(async (): Promise<void> => {
    setIsGpuTypeLoading(true);
    try {
      const { data, error } = await api.GET("/api/conversations/research/gpu-types");
      if (error) throw new Error("Failed to fetch GPU types");
      const response = data as ResearchGpuTypesResponse;
      const list = response.gpu_types ?? [];
      const prices = response.gpu_prices ?? {};
      const displayNames = response.gpu_display_names ?? {};
      const vramGb = response.gpu_vram_gb ?? {};
      setGpuTypes(list);
      setGpuPrices(prices);
      setGpuDisplayNames(displayNames);
      setGpuVramGb(vramGb);
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
      setGpuPrices({});
      setGpuDisplayNames({});
      setGpuVramGb({});
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
    gpuPrices,
    gpuDisplayNames,
    gpuVramGb,
    selectedGpuType,
    isGpuTypeLoading,
    refreshGpuTypes,
    setSelectedGpuType: handleSelectGpuType,
  };
}
