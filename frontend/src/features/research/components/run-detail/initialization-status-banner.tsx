"use client";

import { Loader2 } from "lucide-react";

interface InitializationStatusBannerProps {
  status: string;
  initializationStatus: string;
}

export function InitializationStatusBanner({
  status,
  initializationStatus,
}: InitializationStatusBannerProps) {
  const raw = initializationStatus?.trim() || "pending";
  const text = raw;
  const isActive = status === "initializing";

  if (!isActive) {
    return null;
  }

  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900/50 p-4">
      <div className="flex items-center gap-3">
        <Loader2 className="h-4 w-4 animate-spin text-emerald-400" />
        <div className="flex flex-col">
          <div className="text-sm font-medium text-white">Initializing</div>
          <div className="text-sm text-slate-300">{text}</div>
        </div>
      </div>
    </div>
  );
}
