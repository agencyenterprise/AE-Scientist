"use client";

import { useQuery } from "@tanstack/react-query";
import { Check, ChevronDown, Cpu, Sparkles, X, Zap } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import { fetchModels } from "../api";

interface ModelSelectorProps {
  value: string;
  onChange: (value: string) => void;
}

const PROVIDER_LABELS: Record<string, string> = {
  anthropic: "Anthropic",
  openai: "OpenAI",
  xai: "xAI",
};

const PROVIDER_ORDER = ["anthropic", "openai", "xai"];

function getProviderIcon(provider: string) {
  switch (provider) {
    case "anthropic":
      return <Sparkles className="h-4 w-4" />;
    case "openai":
      return <Zap className="h-4 w-4" />;
    default:
      return <Cpu className="h-4 w-4" />;
  }
}

export function ModelSelector({ value, onChange }: ModelSelectorProps) {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["models"],
    queryFn: fetchModels,
    staleTime: 5 * 60 * 1000,
  });

  // Set default model when data loads
  useEffect(() => {
    if (data?.default && !value) {
      onChange(data.default);
    }
  }, [data, value, onChange]);

  // Close dropdown when clicking outside
  useEffect(() => {
    if (!isOpen) return;

    function handleClickOutside(event: MouseEvent) {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(event.target as Node) &&
        buttonRef.current &&
        !buttonRef.current.contains(event.target as Node)
      ) {
        setIsOpen(false);
      }
    }

    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [isOpen]);

  // Group models by provider
  const groupedModels = useMemo(() => {
    if (!data?.models) return {};

    const groups: Record<string, typeof data.models> = {};
    for (const model of data.models) {
      if (!groups[model.provider]) {
        groups[model.provider] = [];
      }
      groups[model.provider].push(model);
    }
    return groups;
  }, [data]);

  // Get selected model info
  const selectedModel = useMemo(() => {
    return data?.models.find((m) => m.id === value);
  }, [data, value]);

  if (isLoading) {
    return (
      <div className="h-12 bg-slate-800/50 rounded-xl animate-pulse flex items-center px-4">
        <span className="text-slate-400 text-sm">Loading models...</span>
      </div>
    );
  }

  return (
    <div className="relative">
      {/* Dropdown Button */}
      <button
        ref={buttonRef}
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className={`w-full flex items-center justify-between gap-2 sm:gap-3 p-3 sm:p-4 rounded-xl border-2 text-left transition-all duration-200 ${
          isOpen
            ? "border-sky-500 bg-sky-500/10"
            : "border-slate-700/50 bg-slate-900/30 hover:border-slate-600 hover:bg-slate-800/30"
        }`}
      >
        <div className="flex items-center gap-2 sm:gap-3 min-w-0">
          <div
            className={`shrink-0 p-1.5 sm:p-2 rounded-lg ${
              selectedModel
                ? "bg-sky-500/20 text-sky-400"
                : "bg-slate-800 text-slate-400"
            }`}
          >
            {selectedModel ? (
              getProviderIcon(selectedModel.provider)
            ) : (
              <Cpu className="h-4 w-4 sm:h-5 sm:w-5" />
            )}
          </div>
          <div className="min-w-0">
            <div className="font-semibold text-white truncate text-sm sm:text-base">
              {selectedModel?.name || "Select a model"}
            </div>
            {selectedModel && (
              <div className="text-xs text-slate-400 truncate">
                {PROVIDER_LABELS[selectedModel.provider] ||
                  selectedModel.provider}
              </div>
            )}
          </div>
        </div>
        <ChevronDown
          className={`h-5 w-5 text-slate-400 shrink-0 transition-transform duration-200 ${
            isOpen ? "rotate-180" : ""
          }`}
        />
      </button>

      {/* Dropdown Menu */}
      {isOpen && (
        <div
          ref={dropdownRef}
          className="absolute z-50 w-full mt-2 bg-slate-900 border border-slate-700 rounded-xl shadow-xl overflow-hidden"
        >
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 border-b border-slate-700 bg-slate-800/50">
            <span className="text-sm font-medium text-slate-300">
              Select Model
            </span>
            <button
              type="button"
              onClick={() => setIsOpen(false)}
              className="text-slate-400 hover:text-white transition-colors"
            >
              <X className="h-4 w-4" />
            </button>
          </div>

          {/* Model List */}
          <div className="max-h-[60vh] sm:max-h-80 overflow-y-auto">
            {PROVIDER_ORDER.filter((p) => groupedModels[p]?.length > 0).map(
              (provider) => (
                <div key={provider}>
                  {/* Provider Header */}
                  <div className="px-4 py-2 bg-slate-800/80 border-b border-slate-700/50 sticky top-0">
                    <div className="flex items-center gap-2">
                      <span className="text-slate-400">
                        {getProviderIcon(provider)}
                      </span>
                      <span className="text-xs font-semibold text-slate-400 uppercase tracking-wide">
                        {PROVIDER_LABELS[provider] || provider}
                      </span>
                    </div>
                  </div>

                  {/* Models in this provider */}
                  {groupedModels[provider].map((model) => {
                    const isSelected = model.id === value;
                    return (
                      <button
                        key={model.id}
                        type="button"
                        onClick={() => {
                          onChange(model.id);
                          setIsOpen(false);
                        }}
                        className={`w-full flex items-center gap-3 px-4 py-3 text-left transition-colors ${
                          isSelected
                            ? "bg-sky-500/10 border-l-2 border-sky-500"
                            : "hover:bg-slate-800/50 border-l-2 border-transparent"
                        }`}
                      >
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <span
                              className={`font-medium ${isSelected ? "text-sky-400" : "text-slate-200"}`}
                            >
                              {model.name}
                            </span>
                            {isSelected && (
                              <Check className="h-4 w-4 text-sky-400 shrink-0" />
                            )}
                          </div>
                          <p className="text-xs text-slate-500 mt-0.5 line-clamp-1">
                            {model.description}
                          </p>
                        </div>
                      </button>
                    );
                  })}
                </div>
              ),
            )}
          </div>
        </div>
      )}
    </div>
  );
}
