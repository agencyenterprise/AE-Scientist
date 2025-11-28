"use client";

import { Search, MessageSquare } from "lucide-react";

interface ConversationsBoardHeaderProps {
  searchTerm: string;
  onSearchChange: (term: string) => void;
  totalCount: number;
  filteredCount: number;
}

export function ConversationsBoardHeader({
  searchTerm,
  onSearchChange,
  totalCount,
  filteredCount,
}: ConversationsBoardHeaderProps) {
  const showingFiltered = searchTerm.trim() && filteredCount !== totalCount;

  return (
    <div className="flex flex-col gap-6 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex items-center gap-4">
        <div className="flex h-12 w-12 items-center justify-center rounded-2xl border border-sky-500/40 bg-sky-500/15">
          <MessageSquare className="h-6 w-6 text-sky-400" />
        </div>
        <div>
          <h1 className="text-2xl font-semibold text-white sm:text-3xl">Conversations</h1>
          <p className="text-sm text-slate-400">
            {showingFiltered
              ? `Showing ${filteredCount} of ${totalCount} conversations`
              : `${totalCount} conversation${totalCount !== 1 ? "s" : ""}`}
          </p>
        </div>
      </div>

      <div className="relative">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
        <input
          type="text"
          placeholder="Search conversations..."
          value={searchTerm}
          onChange={e => onSearchChange(e.target.value)}
          className="w-full rounded-xl border border-slate-700 bg-slate-900/50 py-2.5 pl-10 pr-4 text-sm text-white placeholder-slate-500 transition-colors focus:border-sky-500/50 focus:outline-none focus:ring-1 focus:ring-sky-500/50 sm:w-72"
        />
      </div>
    </div>
  );
}
