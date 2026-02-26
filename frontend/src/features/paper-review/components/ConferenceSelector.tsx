"use client";

import { cn } from "@/shared/lib/utils";

type Conference = "neurips_2025" | "iclr_2025";

interface ConferenceSelectorProps {
  selectedConference: Conference;
  onConferenceChange: (conference: Conference) => void;
}

const CONFERENCES: { id: Conference; label: string }[] = [
  { id: "neurips_2025", label: "NeurIPS 2025" },
  { id: "iclr_2025", label: "ICLR 2025" },
];

export function ConferenceSelector({
  selectedConference,
  onConferenceChange,
}: ConferenceSelectorProps) {
  return (
    <div className="inline-flex rounded-lg border border-slate-700/60 bg-slate-900/50 p-0.5">
      {CONFERENCES.map(conf => (
        <button
          key={conf.id}
          type="button"
          onClick={() => onConferenceChange(conf.id)}
          className={cn(
            "rounded-md px-3 py-1.5 text-xs font-medium transition-colors",
            selectedConference === conf.id
              ? "bg-slate-700 text-white"
              : "text-slate-400 hover:text-slate-300"
          )}
        >
          {conf.label}
        </button>
      ))}
    </div>
  );
}
