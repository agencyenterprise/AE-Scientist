"use client";

import { useState } from "react";
import { X, Loader2, Plus } from "lucide-react";

interface CreateProjectModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => Promise<void>;
  isLoading?: boolean;
  availableGpuTypes: string[];
  gpuPrices: Record<string, number | null>;
  gpuDisplayNames: Record<string, string>;
  gpuVramGb: Record<string, number | null>;
  selectedGpuType: string | null;
  onSelectGpuType: (gpuType: string) => void;
  isGpuTypeLoading?: boolean;
}

function formatHourlyPrice(price: number | null | undefined): string | null {
  if (price === null || price === undefined) return null;
  if (!Number.isFinite(price)) return null;
  return `$${price.toFixed(2)}/hr`;
}

export function CreateProjectModal({
  isOpen,
  onClose,
  onConfirm,
  isLoading = false,
  availableGpuTypes,
  gpuPrices,
  gpuDisplayNames,
  gpuVramGb,
  selectedGpuType,
  onSelectGpuType,
  isGpuTypeLoading = false,
}: CreateProjectModalProps) {
  const [error, setError] = useState("");
  const isConfirmDisabled = isLoading || isGpuTypeLoading || !selectedGpuType;

  const handleConfirm = async () => {
    setError("");
    if (!selectedGpuType) {
      setError("Select a GPU type before launching research.");
      return;
    }
    try {
      await onConfirm();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create project");
    }
  };

  const handleClose = () => {
    if (!isLoading) {
      setError("");
      onClose();
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black bg-opacity-50">
      <div className="relative bg-card rounded-lg shadow-xl max-w-md w-full">
        <div className="p-6">
          {/* Header */}
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-medium text-foreground">Launch Research</h3>
            <button
              type="button"
              onClick={handleClose}
              disabled={isLoading}
              className="text-muted-foreground hover:text-foreground disabled:opacity-50 p-1 rounded"
            >
              <X className="w-6 h-6" />
            </button>
          </div>

          {/* Content */}
          <div className="mb-6 space-y-4">
            <p className="text-sm text-muted-foreground mb-4">
              This will launch a new research run based on your current work.
            </p>
            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground" htmlFor="gpu-type-select">
                GPU type
              </label>
              {isGpuTypeLoading ? (
                <div className="text-sm text-muted-foreground">Loading GPU options...</div>
              ) : availableGpuTypes.length > 0 ? (
                <select
                  id="gpu-type-select"
                  className="w-full rounded-md border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-[var(--ring)]"
                  value={selectedGpuType ?? ""}
                  onChange={event => {
                    const value = event.target.value;
                    if (value) {
                      onSelectGpuType(value);
                    }
                  }}
                  disabled={isLoading || availableGpuTypes.length === 0}
                >
                  {selectedGpuType === null && (
                    <option value="" disabled>
                      Select a GPU
                    </option>
                  )}
                  {availableGpuTypes.map(gpuType => {
                    const baseName = gpuDisplayNames[gpuType] || gpuType;
                    const vram = gpuVramGb[gpuType];
                    const displayName = vram ? `${baseName} (${vram} GB VRAM)` : baseName;
                    const priceLabel = formatHourlyPrice(gpuPrices[gpuType]);
                    const optionLabel = priceLabel ? `${displayName} — ${priceLabel}` : displayName;
                    return (
                      <option key={gpuType} value={gpuType}>
                        {optionLabel}
                      </option>
                    );
                  })}
                </select>
              ) : (
                <div className="text-sm text-[var(--danger)]">
                  No GPU types are currently available. Please try again later.
                </div>
              )}
            </div>

            <div className="rounded-md border border-slate-700 bg-slate-800/50 p-3 space-y-2">
              <p className="text-sm text-slate-300">
                <span className="font-medium">Typical run:</span> ~$25 USD over 4-6 hours (based on
                a ~$1/hr GPU)
              </p>
              <p className="text-xs text-slate-400">
                If your balance goes negative, results are locked until you add credits.
              </p>
            </div>
          </div>

          {/* Error Message */}
          {error && (
            <div className="mb-4 p-3 bg-[color-mix(in_srgb,var(--danger),transparent_90%)] border border-[var(--danger)] rounded-md">
              <p className="text-sm text-[var(--danger)]">{error}</p>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="bg-muted px-6 py-3 flex flex-row-reverse gap-3">
          <button
            onClick={handleConfirm}
            disabled={isConfirmDisabled}
            className="inline-flex items-center justify-center px-4 py-2 bg-[var(--success)] text-[var(--success-foreground)] text-sm font-medium rounded-md hover:opacity-90 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-[var(--success)] disabled:bg-muted disabled:text-muted-foreground disabled:cursor-not-allowed"
          >
            {isLoading ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                Launching Research...
              </>
            ) : (
              <>
                <Plus className="w-4 h-4 mr-2" />
                Launch Research
              </>
            )}
          </button>
          <button
            onClick={handleClose}
            disabled={isLoading}
            className="inline-flex items-center justify-center px-4 py-2 bg-[var(--surface)] text-[var(--foreground)]/80 text-sm font-medium border border-[var(--border)] rounded-md hover:bg-[var(--muted)] focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-[var(--ring)] disabled:opacity-50"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}
