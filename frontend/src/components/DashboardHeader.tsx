"use client";

import { useDashboard } from "@/app/(dashboard)/DashboardContext";
import { SearchBox } from "@/components/Search";

type DashboardSearchBoxProps = {
  query: string;
  isLoading: boolean;
  placeholder: string;
  onQueryChange: (query: string) => void;
  onSearch: (query: string) => void;
  onClear: () => void;
  disabled: boolean;
};

export function DashboardHeader({ searchBoxProps }: { searchBoxProps?: DashboardSearchBoxProps }) {
  const { isSidebarCollapsed } = useDashboard();

  return (
    <div
      className={`px-6 py-3 bg-[color-mix(in_srgb,var(--surface),transparent_20%)] backdrop-blur supports-[backdrop-filter]:bg-[color-mix(in_srgb,var(--surface),transparent_30%)] border-b border-[var(--border)] sticky top-0 z-10`}
    >
      <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
        <div
          className={`flex items-center gap-3 self-end md:self-auto w-full md:w-auto pl-12 sm:pl-0 ${isSidebarCollapsed ? "md:pl-10" : ""}`}
        >
          {searchBoxProps && (
            <div className="flex-1 md:w-[32rem]">
              <SearchBox {...searchBoxProps} />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
