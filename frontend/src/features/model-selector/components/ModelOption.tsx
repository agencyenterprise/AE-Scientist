"use client";

import type { LLMModel } from "@/types";
import { RefObject } from "react";
import { Image as ImageIcon, FileText, Check } from "lucide-react";

interface ModelOptionProps {
  provider: string;
  model: LLMModel;
  isSelected: boolean;
  isDefault: boolean;
  isCompatible: boolean;
  incompatibilityReason: string | null;
  showCapabilities: boolean;
  onSelect: (provider: string, modelId: string) => void;
  selectedRef?: RefObject<HTMLButtonElement | null>;
}

export function ModelOption({
  provider,
  model,
  isSelected,
  isDefault,
  isCompatible,
  incompatibilityReason,
  showCapabilities,
  onSelect,
  selectedRef,
}: ModelOptionProps) {
  return (
    <button
      type="button"
      ref={isSelected ? selectedRef : null}
      onClick={() => onSelect(provider, model.id)}
      disabled={!isCompatible}
      className={`w-full text-left px-3 py-2 text-xs transition-colors ${
        !isCompatible
          ? "text-muted-foreground/50 cursor-not-allowed opacity-75"
          : isSelected
            ? "bg-primary/10 text-primary font-medium hover:bg-primary/20"
            : isDefault
              ? "bg-green-500/10 hover:bg-green-500/20 border-l-2 border-green-500/50"
              : "text-foreground hover:bg-muted"
      }`}
      title={incompatibilityReason || undefined}
    >
      <div className="flex items-center">
        {/* Model name - flexible width */}
        <div className="flex-1 min-w-0 pr-2">
          <div className="truncate">{model.label}</div>
          {isDefault && <div className="text-xs text-green-600 font-medium">default</div>}
          {incompatibilityReason && (
            <div className="text-xs text-muted-foreground/50 italic truncate">
              {incompatibilityReason}
            </div>
          )}
        </div>

        {/* Capabilities - fixed width for alignment */}
        {showCapabilities && (
          <div className="flex items-center justify-center w-12 space-x-1">
            <span title="Supports images" className="w-4 text-center">
              {model.supports_images && <ImageIcon className="w-3.5 h-3.5 text-muted-foreground" />}
            </span>
            <span title="Supports PDFs" className="w-4 text-center">
              {model.supports_pdfs && <FileText className="w-3.5 h-3.5 text-muted-foreground" />}
            </span>
          </div>
        )}

        {/* Selection checkmark - small fixed width on right */}
        <div className="flex items-center justify-center w-8">
          {isSelected && (
            <Check
              className={`w-4 h-4 ${isCompatible ? "text-primary" : "text-muted-foreground/50"}`}
            />
          )}
        </div>
      </div>
    </button>
  );
}
