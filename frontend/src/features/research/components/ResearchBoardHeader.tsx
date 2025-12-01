"use client";

import { useState, useEffect } from "react";
import { Search, FlaskConical, Loader2 } from "lucide-react";
import { fetchUsers, UserListItem } from "@/shared/lib/api-adapters";

interface ResearchBoardHeaderProps {
  searchTerm: string;
  onSearchChange: (term: string) => void;
  statusFilter: string;
  onStatusFilterChange: (status: string) => void;
  selectedUserId: number | null;
  onSelectedUserIdChange: (userId: number | null) => void;
  currentUserId?: number;
  totalCount: number;
  filteredCount: number;
  isLoading?: boolean;
}

export function ResearchBoardHeader({
  searchTerm,
  onSearchChange,
  statusFilter,
  onStatusFilterChange,
  selectedUserId,
  onSelectedUserIdChange,
  currentUserId,
  totalCount,
  filteredCount,
  isLoading = false,
}: ResearchBoardHeaderProps) {
  const [users, setUsers] = useState<UserListItem[]>([]);
  const [localSearchTerm, setLocalSearchTerm] = useState(searchTerm);

  // Fetch users on mount
  useEffect(() => {
    fetchUsers()
      .then(setUsers)
      .catch(() => {});
  }, []);

  // Keep local search term in sync with prop (for when it resets)
  useEffect(() => {
    setLocalSearchTerm(searchTerm);
  }, [searchTerm]);

  const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setLocalSearchTerm(value);
    onSearchChange(value);
  };

  // Check if "Only mine" mode is active
  const onlyMine = selectedUserId === currentUserId && currentUserId !== undefined;

  const handleOnlyMineToggle = () => {
    if (onlyMine) {
      // Turn off "only mine" - show all
      onSelectedUserIdChange(null);
    } else {
      // Turn on "only mine"
      if (currentUserId) {
        onSelectedUserIdChange(currentUserId);
      }
    }
  };

  const handleUserChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const value = e.target.value;
    onSelectedUserIdChange(value ? Number(value) : null);
  };

  const hasFilters = searchTerm.trim() || statusFilter !== "all" || selectedUserId !== null;

  return (
    <div className="flex flex-col gap-6 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex items-center gap-4">
        <div className="flex h-12 w-12 items-center justify-center rounded-2xl border border-emerald-500/40 bg-emerald-500/15">
          <FlaskConical className="h-6 w-6 text-emerald-400" />
        </div>
        <div>
          <h1 className="text-2xl font-semibold text-white sm:text-3xl">Research Runs</h1>
          <p className="text-sm text-slate-400">
            {isLoading ? (
              <span className="flex items-center gap-2">
                <Loader2 className="h-3 w-3 animate-spin" />
                Loading...
              </span>
            ) : hasFilters ? (
              `Showing ${filteredCount} of ${totalCount} runs`
            ) : (
              `${totalCount} research run${totalCount !== 1 ? "s" : ""}`
            )}
          </p>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        {currentUserId && (
          <label className="flex cursor-pointer items-center gap-2">
            <span className="text-sm text-slate-400">Only mine</span>
            <button
              type="button"
              role="switch"
              aria-checked={onlyMine}
              onClick={handleOnlyMineToggle}
              className={`relative h-6 w-11 rounded-full transition-colors ${
                onlyMine ? "bg-emerald-500" : "bg-slate-700"
              }`}
            >
              <span
                className={`absolute left-0.5 top-0.5 h-5 w-5 rounded-full bg-white transition-transform ${
                  onlyMine ? "translate-x-5" : "translate-x-0"
                }`}
              />
            </button>
          </label>
        )}

        {!onlyMine && (
          <select
            value={selectedUserId ?? ""}
            onChange={handleUserChange}
            className="rounded-xl border border-slate-700 bg-slate-900/50 px-3 py-2.5 text-sm text-white transition-colors focus:border-emerald-500/50 focus:outline-none focus:ring-1 focus:ring-emerald-500/50"
          >
            <option value="">All Users</option>
            {users.map(user => (
              <option key={user.id} value={user.id}>
                {user.name}
              </option>
            ))}
          </select>
        )}

        <select
          value={statusFilter}
          onChange={e => onStatusFilterChange(e.target.value)}
          className="rounded-xl border border-slate-700 bg-slate-900/50 px-3 py-2.5 text-sm text-white transition-colors focus:border-emerald-500/50 focus:outline-none focus:ring-1 focus:ring-emerald-500/50"
        >
          <option value="all">All Status</option>
          <option value="pending">Pending</option>
          <option value="running">Running</option>
          <option value="completed">Completed</option>
          <option value="failed">Failed</option>
        </select>

        <div className="relative">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
          <input
            type="text"
            placeholder="Search runs..."
            value={localSearchTerm}
            onChange={handleSearchChange}
            className="w-full rounded-xl border border-slate-700 bg-slate-900/50 py-2.5 pl-10 pr-4 text-sm text-white placeholder-slate-500 transition-colors focus:border-emerald-500/50 focus:outline-none focus:ring-1 focus:ring-emerald-500/50 sm:w-72"
          />
        </div>
      </div>
    </div>
  );
}
